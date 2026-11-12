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
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from app.models.deployers import DeployerStats
from app.models.book import OrderBook
from app.models.candle import CandleRange, PriceHistory
from app.models.costs import ExecutionEstimate, VenueCost
from app.models.feed import Feed
from app.models.leaderboard import Leaderboard, LeaderboardSort, LeaderboardWindow
from app.models.market import OutcomeMarket, OutcomeMarketDetail
from app.models.venue import (
    ElsewhereEntry,
    LinkGroupCreate,
    Suggestion,
    Venue,
    VenueLink,
    VenueQuote
)
from app.services.analytics import deployer_stats, find_lookalikes
from app.services.history import HistoryRecorder, HistoryStore, bucket_prices
from app.services.execution import hyperliquid_cost, kalshi_cost, polymarket_cost
from app.services.kalshi import KalshiClient, KalshiError, kalshi_levels, kalshi_quote
from app.services.links import DuplicateLinkError, LinkStore
from app.services.polymarket import (
    PolymarketClient, 
    PolymarketError,
    polymarket_levels,
    polymarket_quote,
    yes_token_id,
)
from app.services.suggestions import SuggestionFinder
from app.services.fill_collector import LEADERBOARD_WEIGHT_PER_MINUTE, FillCollector
from app.services.trade_watcher import TradeWatcher
from app.services.feed import FeedService
from app.services.leaderboard import WindowResult, build_leaderboard, compute_window
from app.services.traders import TraderStore
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
        markets = normalize_markets(self.data)
        # Lookalikes compare markets w/ each other, so they can only be 
        # computed once the whole list exists
        lookalikes = find_lookalikes(markets, meta)
        self.markets = [
            market.model_copy(update={"lookalikes": lookalikes[market.id]})
            if market.id in lookalikes
            else market
            for market in markets
        ]
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
    # Other venues (M22), sharing the same connection pool
    app.state.polymarket = PolymarketClient(app.state.http)
    app.state.kalshi = KalshiClient(app.state.http)
    app.state.suggestions = SuggestionFinder(app.state.polymarket, app.state.kalshi)
    # (venue, external_id) -> (fetched_at_monotonic, VenueQuote | None)
    app.state.venue_quotes = {}
    # Execution-cost inputs (22.4): key -> (fetched_at_monotonic, value)
    app.state.execution_cache = {}
    app.state.snapshot = None
    # (fetched_at_monotonic, {template id: template}) or None
    app.state.templates = None
    # Settled markets never change, so this cache has no expiry.
    app.state.settled = {}
    # coin -> (fetched_at_monotonic, OrderBook)
    app.state.books = {}    
    # (coin, range) -> (fetched_at_monotonic, PriceHistory)
    app.state.candles = {}
    # window -> (computed_at_monotonic, WindowResult)
    app.state.leaderboard = {}
    # unified feed: each source caches itself
    app.state.feed = FeedService(app.state.http, app.state.hyperliquid, live_markets)


    # Background book sweep (Milestone 18.3b). create_task starts it
    # running alongside request handling; it never blocks startup.
    app.state.sweeper = BookSweeper(app.state.hyperliquid, side0_coins)
    sweep_task = asyncio.create_task(app.state.sweeper.run_forever())

    
    app.state.history_store = HistoryStore()
    await asyncio.to_thread(app.state.history_store.initialize)
    app.state.link_store = LinkStore()
    await asyncio.to_thread(app.state.link_store.initialize)
    app.state.recorder = HistoryRecorder(
        app.state.history_store, 
        live_markets,
        app.state.hyperliquid.fetch_settled_outcome,
        )
    record_task = asyncio.create_task(app.state.recorder.run_forever())
    # Outcome trader discovery, live trade stream
    app.state.trader_store = TraderStore()
    await asyncio.to_thread(app.state.trader_store.initialize)
    app.state.trade_watcher = TradeWatcher(app.state.trader_store, outcome_coins_by_volume)
    watch_task = asyncio.create_task(app.state.trade_watcher.run_forever())
    # Outcome fills within a fixed REST budget 
    app.state.fill_collector = FillCollector(
        app.state.trader_store, app.state.hyperliquid.fetch_user_fills_by_time
    )
    collect_task = asyncio.create_task(app.state.fill_collector.run_forever())

    yield

    # Shutdown order matters: stop the background tasks before closing the HTTP
    # client they use, then wait for the cancellations.
    for task in (collect_task, watch_task, record_task, sweep_task):
        task.cancel()
    for task in (collect_task, watch_task, record_task, sweep_task):
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await app.state.http.aclose()

app = FastAPI(title="Hyperliquid Outcomes API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite frontend
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST", "DELETE"],
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

async def outcome_coins_by_volume() -> list[str]:
    """Every live outcome coin (both sides), busiest markets first, so a
    subscription cap drops the quietest markets, never the busiest."""
    snapshot = await get_snapshot()
    ranked = sorted(snapshot.markets, key=lambda m: m.volume_24h or 0, reverse=True)
    return [side.coin for market in ranked for side in market.sides]

async def live_markets() -> list[OutcomeMarket]:
    """What the history recorder samples: every market in the snapshot."""
    snapshot = await get_snapshot()
    return snapshot.markets


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

class HistoryStatus(BaseModel):
    """Whether the history recorder is alive and how much it has stored"""

    model_config = ConfigDict(populate_by_name=True)

    last_recorded_at: datetime | None = Field(alias="lastRecordedAt")
    last_batch: int = Field(alias="lastBatch")
    slots_recorded: int = Field(alias="slotsRecorded")
    settlements_recorded: int = Field(alias="settlementsRecorded")
    pending_settlements: int = Field(alias="pendingSettlements")
    file_bytes: int = Field(alias="fileBytes")

class TradeWatchStatus(BaseModel):
    """Whether trader discovery is connected and finding traders (23.1)."""

    model_config = ConfigDict(populate_by_name=True)

    connected: bool
    subscriptions: int
    trades_seen: int = Field(alias="tradesSeen")
    traders_known: int = Field(alias="tradersKnown")
    last_trade_at: datetime | None = Field(alias="lastTradeAt")

class FillCollectStatus(BaseModel):
    """Progress of the trader fill collector (23.2)."""

    model_config = ConfigDict(populate_by_name=True)

    weight_per_minute: int = Field(alias="weightPerMinute")
    traders_collected: int = Field(alias="tradersCollected")
    traders_due: int = Field(alias="tradersDue")
    needs_backfill: int = Field(alias="needsBackfill")  # coverage unknown (23.2b)
    largest_pass_fills: int = Field(alias="largestPassFills")   # served-cap check
    fills_stored: int = Field(alias="fillsStored")
    last_fetch_at: datetime | None = Field(alias="lastFetchAt")

class HealthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    book_sweep: SweepStatus = Field(alias="bookSweep")
    history: HistoryStatus
    trade_watch: TradeWatchStatus = Field(alias="tradeWatch")
    fill_collect: FillCollectStatus = Field(alias="fillCollect")


@app.get("/health", response_model_by_alias=True)
async def health() -> HealthResponse:
    # A background task can die silently; exposing its progress here turns
    # "is it still running?" into something you can check with curl.
    sweeper: BookSweeper = app.state.sweeper
    recorder: HistoryRecorder = app.state.recorder
    store: HistoryStore = app.state.history_store
    watcher: TradeWatcher = app.state.trade_watcher
    collector: FillCollector = app.state.fill_collector
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
         history=HistoryStatus(
            last_recorded_at=(
                datetime.fromtimestamp(recorder.last_recorded_at, tz=timezone.utc)
                if recorder.last_recorded_at is not None
                else None
            ),
            last_batch=recorder.last_batch,
            slots_recorded=recorder.slots_recorded,
            settlements_recorded = recorder.settlements_recorded,
            pending_settlements=recorder.pending_settlements,
            file_bytes=store.file_size(),
        ),
        trade_watch=TradeWatchStatus(
            connected=watcher.connected,
            subscriptions=watcher.subscriptions,
            trades_seen=watcher.trades_seen,
            traders_known=watcher.traders_known,
            last_trade_at=(
                datetime.fromtimestamp(watcher.last_trade_at, tz=timezone.utc)
                if watcher.last_trade_at is not None
                else None
            ),
        ),
         fill_collect=FillCollectStatus(
            weight_per_minute=LEADERBOARD_WEIGHT_PER_MINUTE,
            traders_collected=collector.traders_collected,
            traders_due=collector.due,
            needs_backfill=collector.needs_backfill,
            largest_pass_fills=collector.largest_pass_fills,
            fills_stored=collector.fills_stored,
            last_fetch_at=(
                datetime.fromtimestamp(collector.last_fetch_at, tz=timezone.utc)
                if collector.last_fetch_at is not None
                else None
            ),
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
    if not market_id.isdigit():
        raise HTTPException(status_code=404, detail=f"Unknown market {market_id}")

    preset = RANGE_PRESETS[chart_range]
    # Side 0 only: the books are merged, so side 1's history is exactly
    # 1 - side 0's (verified in the Milestone 19 probe).
    coin = f"#{10 * int(market_id)}"

    snapshot = await get_snapshot()
    if market_id not in snapshot.raw_by_id:
        # Not live: Hyperliquid has deleted its candles (19), so fall
        # back to what this app recorded while it was live (21.3).
        return await recorded_history(market_id, coin, chart_range, preset)

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


# Candle interval -> its length, for bucketing our 5-minute recordings.
INTERVAL_SECONDS = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}


async def recorded_history(
    market_id: str, coin: str, chart_range: CandleRange, preset: RangePreset
) -> PriceHistory:
    """Chart data for a market that is no longer live (Milestone 21.3).

    The range is measured back from the market's LAST usable recording,
    not from now: "1D" of a market that settled last week is its final
    day, which is the day worth seeing.
    """
    store: HistoryStore = app.state.history_store
    rows = await asyncio.to_thread(
        store.recorded_prices, market_id, preset.span_ms // 1000
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Price history for market {market_id} is unavailable: "
                "Hyperliquid removes candles when a market settles, and "
                "this app has no usable recording of it"
            ),
        )
    return PriceHistory(
        market_id=market_id,
        coin=coin,
        range=chart_range,
        interval=preset.interval,
        candles=bucket_prices(rows, INTERVAL_SECONDS[preset.interval]),
        fetched_at=datetime.now(timezone.utc),
        source="recorded",
    )


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



# ---------------------------------------------------------------
# Other venues: curated links and suggestions (Milestone 22.2)
# ---------------------------------------------------------------
# NOTE: POST /links and DELETE /links/{id} are the app's first WRITE
# endpoints. They are unauthenticated because this app runs only on
# localhost; they MUST be protected before it is ever deployed.

# Decision 5: an external quote is reused for 30s, so an open panel
# cannot hammer Polymarket or Kalshi.
VENUE_QUOTE_TTL_SECONDS = 30.0


async def venue_quote(venue: Venue, external_id: str) -> VenueQuote | None:
    """A live quote for one linked market (cached), or None if gone."""
    cache: dict[tuple[str, str], tuple[float, VenueQuote | None]] = app.state.venue_quotes
    cached = cache.get((venue, external_id))
    now = time.monotonic()
    if cached is not None and now - cached[0] < VENUE_QUOTE_TTL_SECONDS:
        return cached[1]
    if venue == "polymarket":
        client: PolymarketClient = app.state.polymarket
        raw = await client.fetch_market(external_id)
        quote = polymarket_quote(raw) if raw is not None else None
    else:
        kalshi: KalshiClient = app.state.kalshi
        raw = await kalshi.fetch_market(external_id)
        quote = kalshi_quote(raw) if raw is not None else None
    cache[(venue, external_id)] = (now, quote)
    return quote


@app.get("/markets/{market_id}/links")
async def market_links(market_id: str) -> list[VenueLink]:
    store: LinkStore = app.state.link_store
    return await asyncio.to_thread(store.links_for_market, market_id)


@app.get("/markets/{market_id}/elsewhere")
async def market_elsewhere(market_id: str) -> list[ElsewhereEntry]:
    """Each confirmed link of this outcome with its live quote.

    A venue failing affects only its own entry (error set, quote None):
    one slow or broken venue never blanks the others.
    """
    store: LinkStore = app.state.link_store
    links = await asyncio.to_thread(store.links_for_market, market_id)
    entries = []
    for link in links:
        try:
            quote = await venue_quote(link.venue, link.external_id)
            error = None if quote is not None else "Market no longer listed on this venue"
        except (PolymarketError, KalshiError) as exc:
            quote, error = None, str(exc)
        entries.append(ElsewhereEntry(link=link, quote=quote, error=error))
    return entries


@app.get("/questions/{question_id}/suggestions")
async def question_suggestions(question_id: str) -> list[Suggestion]:
    """Candidate matches on other venues for one football question.

    Nothing is saved: a person compares the rules and confirms with
    POST /links. Questions outside the scope (decision 3) return [].
    """
    snapshot = await get_snapshot()
    members = [m for m in snapshot.markets if m.parent and m.parent.id == question_id]
    if not members:
        raise HTTPException(status_code=404, detail=f"Unknown live question {question_id}")
    finder: SuggestionFinder = app.state.suggestions
    return await finder.find(members)


@app.post("/links", status_code=201)
async def create_links(group: LinkGroupCreate) -> list[VenueLink]:
    """Confirm a match: every outcome link of the group, all or nothing."""
    if group.match_level == "comparable" and not group.note.strip():
        raise HTTPException(
            status_code=422,
            detail="A comparable link needs a note saying how the venues differ",
        )
    store: LinkStore = app.state.link_store
    try:
        return await asyncio.to_thread(store.create_group, group)
    except DuplicateLinkError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"An outcome in this group is already linked to {group.venue} ({exc})",
        ) from exc


@app.delete("/links/{link_id}", status_code=204)
async def delete_link(link_id: int) -> Response:
    store: LinkStore = app.state.link_store
    if not await asyncio.to_thread(store.delete, link_id):
        raise HTTPException(status_code=404, detail=f"No link {link_id}")
    return Response(status_code=204)



# ---------------------------------------------------------------
# Execution costs (Milestone 22.4)
# ---------------------------------------------------------------

# How long each input is reused. Books move, so 10 s; fee schedules
# change rarely, so an hour (Hyperliquid) or a day (Kalshi series).
BOOK_INPUT_TTL = 10.0
MARKET_INPUT_TTL = 60.0
HL_FEES_TTL = 3600.0
KALSHI_SERIES_TTL = 24 * 3600.0
EMPTY_ADDRESS = "0x" + "0" * 40  # no history: userFees returns BASE rates

EXECUTION_ASSUMPTIONS = [
    "Buying the outcome's Yes side by crossing the book now (taker orders).",
    "Each venue's base fee rate; your own tier or discounts may be lower.",
    "Books as of the times shown; prices can move before an order arrives.",
    "Prices and fees in dollars per $1 contract.",
]


async def cached_input(key: tuple, ttl: float, fetch):
    """Reuse a fetched input for `ttl` seconds (keyed by venue + id)."""
    cache: dict[tuple, tuple[float, object]] = app.state.execution_cache
    hit = cache.get(key)
    now = time.monotonic()
    if hit is not None and now - hit[0] < ttl:
        return hit[1]
    value = await fetch()
    cache[key] = (now, value)
    return value


async def hyperliquid_execution(market: OutcomeMarket, raw: dict, size: float) -> VenueCost:
    book = await market_book(market.id, 0)
    client: HyperliquidClient = app.state.hyperliquid
    fees = await cached_input(
        ("hyperliquid", "userFees"), HL_FEES_TTL, lambda: client.fetch_user_fees(EMPTY_ADDRESS)
    )
    try:
        scale = float(raw.get("deployerFeeScale") or 0)
    except ValueError:
        scale = 0.0
    return hyperliquid_cost(
        title=market.question,
        asks=[(level.price, level.size) for level in book.asks],
        bids=[(level.price, level.size) for level in book.bids],
        size=size,
        taker_rate=float(fees["userSpotCrossRate"]),
        deployer_fee_scale=scale,
        book_time=book.fetched_at,
    )


async def polymarket_execution(link: VenueLink, size: float) -> VenueCost:
    client: PolymarketClient = app.state.polymarket
    raw = await cached_input(
        ("polymarket", "market", link.external_id),
        MARKET_INPUT_TTL,
        lambda: client.fetch_market(link.external_id),
    )
    if raw is None:
        raise PolymarketError("Market no longer listed on Polymarket")
    token = yes_token_id(raw)
    if token is None:
        raise PolymarketError("Market has no order-book token")
    book = await cached_input(
        ("polymarket", "book", token), BOOK_INPUT_TTL, lambda: client.fetch_book(token)
    )
    asks, bids = polymarket_levels(book)
    schedule = raw.get("feeSchedule") if raw.get("feesEnabled") else None
    schedule = schedule if isinstance(schedule, dict) else {}
    try:
        book_time = datetime.fromtimestamp(int(book["timestamp"]) / 1000, tz=timezone.utc)
    except (KeyError, TypeError, ValueError):
        book_time = datetime.now(timezone.utc)
    return polymarket_cost(
        external_id=link.external_id,
        title=str(raw.get("question", "")),
        match_level=link.match_level,
        asks=asks,
        bids=bids,
        size=size,
        rate=float(schedule.get("rate") or 0),
        exponent=float(schedule.get("exponent") or 1),
        min_order_size=float(raw["orderMinSize"]) if raw.get("orderMinSize") else None,
        book_time=book_time,
    )


async def kalshi_execution(link: VenueLink, size: float) -> VenueCost:
    client: KalshiClient = app.state.kalshi
    raw = await cached_input(
        ("kalshi", "market", link.external_id),
        MARKET_INPUT_TTL,
        lambda: client.fetch_market(link.external_id),
    )
    if raw is None:
        raise KalshiError("Market no longer listed on Kalshi")
    book = await cached_input(
        ("kalshi", "book", link.external_id),
        BOOK_INPUT_TTL,
        lambda: client.fetch_orderbook(link.external_id),
    )
    asks, bids = kalshi_levels(book)
    # A Kalshi ticker starts with its series: KXEPLGAME-26NOV08IPSBOU-TIE.
    series_ticker = link.external_id.split("-")[0]
    series = await cached_input(
        ("kalshi", "series", series_ticker),
        KALSHI_SERIES_TTL,
        lambda: client.fetch_series_info(series_ticker),
    )
    quote = kalshi_quote(raw)
    return kalshi_cost(
        external_id=link.external_id,
        title=quote.title,
        match_level=link.match_level,
        asks=asks,
        bids=bids,
        size=size,
        fee_type=str(series.get("fee_type", "")),
        fee_multiplier=float(series.get("fee_multiplier") or 1),
        book_time=datetime.now(timezone.utc),
    )


@app.get("/markets/{market_id}/execution")
async def market_execution(
    market_id: str,
    size: float = Query(gt=0, le=1_000_000),
) -> ExecutionEstimate:
    """What buying `size` contracts would cost on Hyperliquid and on
    every confirmed link (Milestone 22.4). One venue failing only marks
    its own row with an error."""
    snapshot = await get_snapshot()
    market = next((m for m in snapshot.markets if m.id == market_id), None)
    if market is None:
        raise HTTPException(status_code=404, detail=f"Market {market_id} is not a live market")

    venues: list[VenueCost] = []
    try:
        venues.append(await hyperliquid_execution(market, snapshot.raw_by_id[market_id], size))
    except (HyperliquidError, HTTPException, KeyError, ValueError) as exc:
        venues.append(VenueCost(venue="hyperliquid", external_id=None, title=market.question,
                                match_level=None, error=str(getattr(exc, "detail", exc))))

    store: LinkStore = app.state.link_store
    for link in await asyncio.to_thread(store.links_for_market, market_id):
        estimate = polymarket_execution if link.venue == "polymarket" else kalshi_execution
        try:
            venues.append(await estimate(link, size))
        except (PolymarketError, KalshiError, KeyError, ValueError) as exc:
            venues.append(VenueCost(venue=link.venue, external_id=link.external_id, title="",
                                    match_level=link.match_level, error=str(exc)))

    return ExecutionEstimate(
        market_id=market_id,
        size=size,
        settles_at=market.event_at or market.resolves_by,
        assumptions=EXECUTION_ASSUMPTIONS,
        venues=venues,
    )


# Manual linking (Milestone 22.5): suggestions only cover football, so
# any other market is linked by pasting the other venue's market.
MAX_LOOKUP_RESULTS = 12


@app.get("/venues/{venue}/lookup")
async def venue_lookup(
    venue: Venue,
    ref: str = Query(min_length=1, max_length=300),
) -> list[VenueQuote]:
    """The other venue's market(s) for a pasted link, id, ticker or words.

    Returns quotes with their full rules, so the person can check they
    have the right market before confirming a link with POST /links.
    """
    try:
        if venue == "polymarket":
            polymarket: PolymarketClient = app.state.polymarket
            quotes = [polymarket_quote(raw) for raw in await polymarket.find_markets(ref)]
        else:
            kalshi: KalshiClient = app.state.kalshi
            quotes = [kalshi_quote(raw) for raw in await kalshi.find_markets(ref)]
    except (PolymarketError, KalshiError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return quotes[:MAX_LOOKUP_RESULTS]

# ---------------------------------------------------------------
# Trader leaderboard (Milestone 23.3)
# ---------------------------------------------------------------
# 23.3a probe: one window's aggregation scans every stored fill (about
# 300 ms at 1.9M fills, and the table keeps growing). So each window is
# computed at most once per TTL, off the event loop, and every sort and
# limit is served from that one result.
LEADERBOARD_TTL_SECONDS = 60.0


@app.get("/leaderboard")
async def leaderboard(
    window: LeaderboardWindow = "30d",
    sort: LeaderboardSort = "pnl",
    limit: int = Query(default=100, ge=1, le=500),
) -> Leaderboard:
    """Traders ranked by realized PnL net of fees (or volume, fills).

    Only traders this app has discovered and fetched are ranked; each
    row says whether its history covers the whole window.
    """
    cache: dict[str, tuple[float, WindowResult]] = app.state.leaderboard
    cached = cache.get(window)
    if cached is not None and time.monotonic() - cached[0] < LEADERBOARD_TTL_SECONDS:
        result = cached[1]
    else:
        store: TraderStore = app.state.trader_store
        result = await asyncio.to_thread(compute_window, store, window)
        cache[window] = (time.monotonic(), result)
    return build_leaderboard(result, window, sort, limit)

# ---------------------------------------------------------------
# Unified feed (Milestone 24)
# ---------------------------------------------------------------

@app.get("/feed")
async def feed() -> Feed:
    """News, sports, ticker and trending items, interleaved.

    Each source refreshes on its own interval and fails on its own:
    `sources` says which worked, so a dead source never empties the feed.
    """
    service: FeedService = app.state.feed
    return await service.feed()