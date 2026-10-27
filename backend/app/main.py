"""FastAPI application serving normalized Hyperliquid outcome markets."""

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from app.models.deployers import DeployerStats
from app.models.book import OrderBook
from app.models.candle import CandleRange, PriceHistory
from app.models.market import OutcomeMarket, OutcomeMarketDetail
from app.services.analytics import deployer_stats
from app.services.sweep import BookSweeper
from app.services.hyperliquid import HyperliquidClient, HyperliquidError
from app.services.normalize import (
    MarketData,
    TopOfBook,
    index_outcome_ctxs,
    index_templates,
    normalize_candles,
    normalize_market_detail,
    normalize_markets,
    normalize_order_book,
    normalize_settled_detail,
)

logger = logging.getLogger(__name__)

# One snapshot refresh costs rate-limit weight 42 (budget: 1200/min):
# outcomeMeta 20 + allMids 2 + spotMetaAndAssetCtxs 20. Caching for 15s
# caps us at ~168 weight/min no matter how many browser tabs are
# refreshing, and market metadata rarely changes that fast.
CACHE_TTL_SECONDS = 15.0

# Templates change only through validator governance votes, so an hourly
# refresh is plenty.
TEMPLATES_TTL_SECONDS = 3600.0

# Order books are constantly changing, but rapid re-clicks on the same markets
# shouldn't each cost an upstream request. l2Book info request is weight 2
BOOK_TTL_SECONDS = 3.0

HOUR_MS = 3_600_000
DAY_MS = 24 * HOUR_MS


@dataclass(frozen=True)
class RangePreset:
    interval: str  # Hyperliquid candle interval
    span_ms: int  # how far back the chart reaches
    ttl: float  # seconds to cache: longer intervals change more slowly


# Sampling (Milestone 19.1): each chart range uses a candle interval that
# gives it a sensible number of points, 96 to at most 365, instead of
# fetching fine candles and thinning them out ourselves.
RANGE_PRESETS: dict[CandleRange, RangePreset] = {
    "1d": RangePreset(interval="15m", span_ms=DAY_MS, ttl=60.0),  # 96
    "1w": RangePreset(interval="1h", span_ms=7 * DAY_MS, ttl=120.0),  # 168
    "1m": RangePreset(interval="4h", span_ms=30 * DAY_MS, ttl=300.0),  # 180
    "all": RangePreset(interval="1d", span_ms=365 * DAY_MS, ttl=600.0),  # <= 365
}

class Snapshot:
    """One consistent view of Hyperliquid data, fetched at a single moment.

    Both the list and detail endpoints read from the same snapshot, so
    they can never disagree with each other.
    """

    def __init__(
        self,
        meta: dict[str, Any],
        mids: dict[str, str],
        ctxs: dict[str, dict[str, Any]],
        templates: dict[str, dict[str, Any]],
        tops: dict[str, TopOfBook],
    ) -> None:
        self.data = MarketData(
            meta,
            mids,
            ctxs,
            templates,
            # Copied: the sweep keeps updating its dict, but a snapshot
            # must stay one consistent view.
            tops=dict(tops),
            as_of=time.time(),
        )
        self.markets = normalize_markets(self.data)
        self.raw_by_id = {
            str(raw.get("outcome")): raw for raw in meta.get("outcomes", [])
        }
        self.fetched_at = time.monotonic()

    def is_fresh(self) -> bool:
        return time.monotonic() - self.fetched_at < CACHE_TTL_SECONDS


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create app-lifetime resources at startup; release them at shutdown."""
    app.state.http = httpx.AsyncClient()
    app.state.hyperliquid = HyperliquidClient(app.state.http)
    app.state.snapshot = None
    # (fetched_at_monotonic, {template id: template}) or None
    app.state.templates = None
    # Settled markets never change, so this cache has no expiry.
    app.state.settled = {}
    # coin -> (fetched_at_monotonic, OrderBook)
    app.state.books = {}    
    # (coin, range) -> (fetched_at_monotonic, PriceHistory)
    app.state.candles = {}


    # Background book sweep (Milestone 18.3b). create_task starts it
    # running alongside request handling; it never blocks startup.
    app.state.sweeper = BookSweeper(app.state.hyperliquid, side0_coins)
    sweep_task = asyncio.create_task(app.state.sweeper.run_forever())

    yield

    # Shutdown order matters: stop the sweep BEFORE closing the HTTP
    # client it uses, then wait for the cancellation to finish.
    sweep_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await sweep_task
    await app.state.http.aclose()


app = FastAPI(title="Hyperliquid Outcomes API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite frontend
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


async def get_templates() -> dict[str, dict[str, Any]]:
    """Return outcome templates, refetching at most once an hour.

    Templates are an enrichment: on failure, keep using the last good
    set, or none at all (titles then fall back to the old wording).
    """
    cached: tuple[float, dict[str, dict[str, Any]]] | None = app.state.templates
    if cached is not None and time.monotonic() - cached[0] < TEMPLATES_TTL_SECONDS:
        return cached[1]

    client: HyperliquidClient = app.state.hyperliquid
    try:
        templates = index_templates(await client.fetch_outcome_templates())
    except HyperliquidError as exc:
        logger.warning("Outcome templates unavailable: %s", exc)
        return cached[1] if cached is not None else {}

    app.state.templates = (time.monotonic(), templates)
    return templates


async def side0_coins() -> list[str]:
    """Coins for the book sweep: side 0 of every live market.

    HL merges each market's two books into one. Per HIP-4 docs,
    buying Yes at p is equivalent to selling No at 1-p. Thus, side 0's
    book describes both sides. Observed in m18.3b: liquid markets mirror
    exactly; fast near-expiry books can differ between two separate 
    requests only because the book moved in between.
    """
    snapshot = await get_snapshot()
    return [m.sides[0].coin for m in snapshot.markets if m.sides]


async def get_snapshot() -> Snapshot:
    """Return a fresh snapshot, refetching when the cache has expired."""
    current: Snapshot | None = app.state.snapshot
    if current is not None and current.is_fresh():
        return current

    client: HyperliquidClient = app.state.hyperliquid
    try:
        meta = await client.fetch_outcome_meta()
        mids = await client.fetch_all_mids()
    except HyperliquidError as exc:
        if current is not None:
            # Hyperliquid is unreachable but we have recent data:
            # stale markets beat an error page.
            return current
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Volume is an enrichment, not a requirement: if this request fails,
    # serve markets without volume rather than failing the whole list.
    try:
        ctxs = index_outcome_ctxs(await client.fetch_spot_asset_ctxs())
    except HyperliquidError as exc:
        logger.warning("Serving markets without volume: %s", exc)
        ctxs = {}

    templates = await get_templates()

    sweeper: BookSweeper = app.state.sweeper
    fresh = Snapshot(meta, mids, ctxs, templates, sweeper.tops)
    app.state.snapshot = fresh
    return fresh


class SweepStatus(BaseModel):
    """Whether the background book sweep is alive and how complete it is."""

    model_config = ConfigDict(populate_by_name=True)

    coins_tracked: int = Field(alias="coinsTracked")
    last_completed_at: datetime | None = Field(alias="lastCompletedAt")
    last_failures: int = Field(alias="lastFailures")


class HealthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    book_sweep: SweepStatus = Field(alias="bookSweep")


@app.get("/health", response_model_by_alias=True)
async def health() -> HealthResponse:
    # A background task can die silently; exposing its progress here turns
    # "is it still running?" into something you can check with curl.
    sweeper: BookSweeper = app.state.sweeper
    completed = sweeper.last_completed_at
    return HealthResponse(
        status="ok",
        book_sweep=SweepStatus(
            coins_tracked=len(sweeper.tops),
            last_completed_at=(
                datetime.fromtimestamp(completed, tz=timezone.utc)
                if completed is not None
                else None
            ),
            last_failures=sweeper.last_failures,
        ),
    )


@app.get("/markets")
async def markets() -> list[OutcomeMarket]:
    snapshot = await get_snapshot()
    return snapshot.markets


@app.get("/markets/{market_id}")
async def market_detail(market_id: str) -> OutcomeMarketDetail:
    snapshot = await get_snapshot()

    # 1. Live market: served from the snapshot.
    raw = snapshot.raw_by_id.get(market_id)
    if raw is not None:
        return normalize_market_detail(raw, snapshot.data)

    # 2. Previously fetched settled market: served from the permanent cache.
    settled_cache: dict[str, OutcomeMarketDetail] = app.state.settled
    cached = settled_cache.get(market_id)
    if cached is not None:
        return cached

    # 3. Not live, not cached. Only ask Hyperliquid if the id could exist;
    #    a non-numeric id is not worth a weight-20 upstream request.
    if not market_id.isdigit():
        raise HTTPException(
            status_code=404, detail=f"Market {market_id} not found"
        )

    client: HyperliquidClient = app.state.hyperliquid
    try:
        settled = await client.fetch_settled_outcome(int(market_id))
    except HyperliquidError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if settled is None:
        raise HTTPException(
            status_code=404, detail=f"Market {market_id} not found"
        )

    detail = normalize_settled_detail(settled, snapshot.data)
    settled_cache[market_id] = detail
    return detail

@app.get("/markets/{market_id}/book")
async def market_book(
    market_id: str,
    side: int = Query(default=0, ge=0, le=1),
) -> OrderBook:
    snapshot = await get_snapshot()
    if market_id not in snapshot.raw_by_id:
        raise HTTPException(
            status_code=404,
            detail=f"Market {market_id} is not a live market",
        )

    coin = f"#{10 * int(market_id) + side}"

    books: dict[str, tuple[float, OrderBook]] = app.state.books
    cached = books.get(coin)
    now = time.monotonic()
    if cached is not None and now - cached[0] < BOOK_TTL_SECONDS:
        return cached[1]

    client: HyperliquidClient = app.state.hyperliquid
    try:
        raw_book = await client.fetch_l2_book(coin)
    except HyperliquidError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    book = normalize_order_book(raw_book, side)
    books[coin] = (now, book)
    return book


@app.get("/markets/{market_id}/candles")
async def market_candles(
    market_id: str,
    # The query parameter is called "range", but `range` is a Python
    # builtin, so the function argument gets a different name + alias.
    chart_range: CandleRange = Query(default="1w", alias="range"),
) -> PriceHistory:
    snapshot = await get_snapshot()
    if market_id not in snapshot.raw_by_id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Price history for market {market_id} is unavailable: "
                "Hyperliquid removes candles when a market settles"
            ),
        )

    preset = RANGE_PRESETS[chart_range]
    # Side 0 only: the books are merged, so side 1's history is exactly
    # 1 - side 0's (verified in the Milestone 19 probe).
    coin = f"#{10 * int(market_id)}"

    cache: dict[tuple[str, str], tuple[float, PriceHistory]] = app.state.candles
    cached = cache.get((coin, chart_range))
    now = time.monotonic()
    if cached is not None and now - cached[0] < preset.ttl:
        return cached[1]

    end_ms = int(time.time() * 1000)
    client: HyperliquidClient = app.state.hyperliquid
    try:
        raw = await client.fetch_candles(
            coin, preset.interval, end_ms - preset.span_ms, end_ms
        )
    except HyperliquidError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    history = PriceHistory(
        market_id=market_id,
        coin=coin,
        range=chart_range,
        interval=preset.interval,
        candles=normalize_candles(raw),
        fetched_at=datetime.now(timezone.utc),
    )
    cache[(coin, chart_range)] = (now, history)
    return history


@app.get("/deployers")
async def deployers() -> list[DeployerStats]:
    """Per-deployer summary of the current snapshot (Milestone 20.1).

    Computed on each request: a few hundred markets take well under a
    millisecond to summarize, so caching would add code for no gain.
    """
    snapshot = await get_snapshot()
    return deployer_stats(
        snapshot.markets, snapshot.data.meta, datetime.now(timezone.utc)
    )