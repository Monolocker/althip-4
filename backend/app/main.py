"""FastAPI application serving normalized Hyperliquid outcome markets."""

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.models.market import OutcomeMarket, OutcomeMarketDetail
from app.services.hyperliquid import HyperliquidClient, HyperliquidError
from app.services.normalize import (
    normalize_market_detail,
    normalize_markets,
    normalize_settled_detail,
)

# One fetch of outcomeMeta costs rate-limit weight 20 (budget: 1200/min).
# Caching for 15s caps us at ~88 weight/min no matter how many browser
# tabs are refreshing, and market metadata rarely changes that fast.
CACHE_TTL_SECONDS = 15.0


class Snapshot:
    """One consistent view of Hyperliquid data, fetched at a single moment.

    Both the list and detail endpoints read from the same snapshot, so
    they can never disagree with each other.
    """

    def __init__(self, meta: dict[str, Any], mids: dict[str, str]) -> None:
        self.meta = meta
        self.mids = mids
        self.markets = normalize_markets(meta, mids)
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
    # Settled markets never change, so this cache has no expiry.
    app.state.settled = {}
    yield
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

    fresh = Snapshot(meta, mids)
    app.state.snapshot = fresh
    return fresh


class HealthResponse(BaseModel):
    status: str


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


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
        return normalize_market_detail(raw, snapshot.mids, snapshot.meta)

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

    detail = normalize_settled_detail(settled, snapshot.meta)
    settled_cache[market_id] = detail
    return detail