"""FastAPI app serving normalized HL outcome markets."""

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.models.market import OutcomeMarket
from app.services.hyperliquid import HyperliquidClient, HyperliquidError
from app.services.normalize import normalize_markets

# One outcomeMeta fetch costs rate-limit weight 20 (budget: 1200/min)
# Caching for 15s caps at ~88 weight/min no matter how many browser
# tabs are refreshing. Market metadata does not change that fast nonetheless
CACHE_TTL_SECONDS = 15.0

class MarketsCache:
    """The most recently normalized market list, with its fetch time."""
    def __init__(self) -> None: 
        self.markets: list[OutcomeMarket] | None = None
        self.fetched_at: float = 0.0

    def is_fresh(self) -> bool:
        return (
            self.markets is not None
            and time.monotonic() - self.fetched_at < CACHE_TTL_SECONDS
        )
    
    def store(self, markets: list[OutcomeMarket]) -> None: 
        self.markets = markets
        self.fetched_at = time.monotonic()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """"Create app-lifetime resources at startup; release them at shutdown.

    Everything before 'yield' runs once when the server starts;
    everything after runs once when it stops.
    """
    app.state.http = httpx.AsyncClient()
    app.state.hyperliquid = HyperliquidClient(app.state.http)
    app.state.cache = MarketsCache()
    yield
    await app.state.http.aclose()


app = FastAPI(title="Hyperliquid Outcomes API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", # Vite frontend
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str

@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")

@app.get("/markets")
async def markets() -> list[OutcomeMarket]:
    cache: MarketsCache = app.state.cache
    if cache.is_fresh():
        return cache.markets
    
    client: HyperliquidClient = app.state.hyperliquid 
    try:
        meta = await client.fetch_outcome_meta()
        mids = await client.fetch_all_mids()
    except HyperliquidError as exc:
        if cache.markets is not None:
            # Hyperliquid is unreachable but app has most recent data
            # stale markets > error page
            return cache.markets
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    
    normalized = normalize_markets(meta, mids)
    cache.store(normalized)
    return normalized