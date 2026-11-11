"""Collecting discovered traders' outcome fills (Milestone 23.2).

The leaderboard needs each trader's fills (realized PnL, fees,
settlements). Fills can only be fetched per address over REST, so this
task spends a FIXED rate-limit budget (decision 2, 23.1) and decides
who to fetch next.

Hyperliquid limits that shape it:
  - REST weight 1200/min per IP; userFillsByTime costs 20 plus 1 per
    20 fills returned (docs).
  - At most FILLS_PAGE_LIMIT fills per response (observed: exactly 2000).
  - Only an address's most recent fills are served at all, so for very
    active traders the 30-day backfill is incomplete; coverage_from
    records how far back each trader's fills really are complete.
"""

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.traders import TraderStore

logger = logging.getLogger(__name__)

# Decision 2 (23.1): the leaderboard's share of the 1200/min REST budget.
LEADERBOARD_WEIGHT_PER_MINUTE = 500
FILLS_PAGE_LIMIT = 2000
BACKFILL_DAYS = 30  # first fetch covers the longest leaderboard window
MAX_PAGES_PER_TURN = 8  # per trader per pass; the rest continues later
# Hyperliquid serves only an address's most recent fills (about 10,000 per
# its docs, to be confirmed in the 23.2 verification). A backfill that
# reaches this many is treated as cut off at its oldest fill.
HL_FILLS_SERVED_CAP = 10_000
RECHECK_HOURS = 6  # re-fetch quiet traders: positions may have settled
OVERLAP_MS = 60_000  # re-read the last minute; duplicates are ignored
IDLE_SECONDS = 20.0  # when nobody is due, look again after this

FetchFills = Callable[[str, int, int], Awaitable[list[dict[str, Any]]]]


def fills_weight(count: int) -> int:
    """Rate-limit weight of one userFillsByTime response."""
    return 20 + math.ceil(count / 20)


class TokenBucket:
    """A rate limiter: `rate` tokens per minute, spent per request.

    Tokens refill continuously up to `capacity`; a request waits until
    enough have accumulated. Charging the ACTUAL cost after a response
    keeps the long-run average at the budget even though a request's
    size is unknown until it returns.
    """

    def __init__(self, rate_per_minute: float, capacity: float) -> None:
        self.rate = rate_per_minute / 60.0
        self.capacity = capacity
        self.tokens = capacity
        self.updated = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
        self.updated = now

    async def acquire(self, amount: float) -> None:
        while True:
            self._refill()
            if self.tokens >= amount:
                return
            await asyncio.sleep((amount - self.tokens) / self.rate)

    def spend(self, amount: float) -> None:
        self._refill()
        self.tokens -= amount  # may go negative: the next acquire waits


class FillCollector:
    def __init__(
        self,
        store: TraderStore,
        fetch_fills: FetchFills,
        weight_per_minute: float = LEADERBOARD_WEIGHT_PER_MINUTE,
    ) -> None:
        self._store = store
        self._fetch = fetch_fills
        # Capacity of one full page, so the collector never bursts much
        # above its per-minute share.
        self._bucket = TokenBucket(weight_per_minute, fills_weight(FILLS_PAGE_LIMIT))
        self.traders_collected = 0
        self.fills_stored = 0
        self.due = 0
        self.last_fetch_at: float | None = None

    async def run_forever(self) -> None:
        """Fetch due traders forever; one failure never stops the loop."""
        while True:
            try:
                worked = await self._collect_batch()
            except Exception:
                logger.exception("Fill collection failed; continuing")
                worked = False
            if not worked:
                await asyncio.sleep(IDLE_SECONDS)

    async def _collect_batch(self) -> bool:
        stale_before = datetime.now(timezone.utc) - timedelta(hours=RECHECK_HOURS)
        due = await asyncio.to_thread(self._store.due_traders, stale_before, 50)
        self.due = len(due)
        for address, fills_through in due:
            try:
                await self._collect(address, fills_through)
            except Exception:
                # One trader's failure (bad response, network) is logged
                # and retried on a later pass; the others continue.
                logger.exception("Fill fetch failed for %s", address)
        return bool(due)

    async def _collect(self, address: str, fills_through: int | None) -> None:
        now = int(time.time() * 1000)
        backfill_start = now - BACKFILL_DAYS * 86_400_000
        start = backfill_start if fills_through is None else max(backfill_start, fills_through - OVERLAP_MS)
        complete_from, complete = await self._fetch_window(address, start, now)
        # Forward progress: everything up to `now` is stored when the
        # window completed; otherwise keep the old mark and retry later.
        through = now if complete else (fills_through or start)
        coverage = None if fills_through is not None else complete_from
        await asyncio.to_thread(self._store.mark_collected, address, through, coverage)
        self.traders_collected += 1
        self.last_fetch_at = time.time()

    async def _fetch_window(self, address: str, start: int, end: int) -> tuple[int, bool]:
        """Fetch every fill in [start, end], however Hyperliquid pages them.

        A full page (FILLS_PAGE_LIMIT fills) means more fills exist in
        the window, below its oldest fill or above its newest, depending
        on which end Hyperliquid filled the page from. Rather than assume
        an order, both remaining parts are queued; a part whose page adds
        nothing new is already stored. Returns (earliest time from which
        fills are complete, whether the whole window was finished).
        """
        pending = [(start, end)]
        fetched = 0
        oldest_seen = end
        pages = 0
        while pending:
            if pages >= MAX_PAGES_PER_TURN:
                return oldest_seen, False  # continue on a later pass
            low, high = pending.pop()
            await self._bucket.acquire(fills_weight(FILLS_PAGE_LIMIT))
            fills = await self._fetch(address, low, high)
            pages += 1
            self._bucket.spend(fills_weight(len(fills)))
            added = await asyncio.to_thread(self._store.save_fills, address, fills)
            self.fills_stored += added
            fetched += len(fills)

            times = [int(f["time"]) for f in fills if "time" in f]
            if times:
                oldest_seen = min(oldest_seen, min(times))
            if len(fills) < FILLS_PAGE_LIMIT or added == 0 or not times:
                continue  # this part is complete (or already stored)
            oldest, newest = min(times), max(times)
            # Inclusive bounds: fills sharing a millisecond with the page
            # edge are fetched again and ignored as duplicates.
            if newest < high:
                pending.append((newest, high))
            if oldest > low:
                pending.append((low, oldest))

        # Every part answered. If the trader hit Hyperliquid's cap on
        # served fills, anything older simply was not available, so the
        # fills are complete only from the oldest one received.
        if fetched >= HL_FILLS_SERVED_CAP:
            return oldest_seen, True
        return start, True