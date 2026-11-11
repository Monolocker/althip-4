"""Collecting discovered traders' outcome fills (Milestones 23.2, 23.2b).

The leaderboard needs each trader's fills (realized PnL, fees,
settlements). Fills can only be fetched per address over REST, so this
task spends a FIXED rate-limit budget (decision 2, 23.1) and decides
who to fetch next.

Hyperliquid limits that shape it:
  - REST weight 1200/min per IP; userFillsByTime costs 20 plus 1 per
    20 fills returned (docs).
  - At most FILLS_PAGE_LIMIT fills per response (observed: exactly 2000).
  - Only an address's 10,000 most recent fills are served at all (docs;
    23.2b probe: nothing older than the oldest served fill came back),
    so for very active traders the 30-day backfill is incomplete;
    coverage_from records how far back each trader's fills really are
    complete.

Verified by the 23.2b probe (the docs disagree with each other):
  - A full page holds the OLDEST fills of the window, oldest first, so
    paging forward from the newest fill received walks the window in
    order. startTime is inclusive: the boundary fill comes back again.
  - Responses include the address's perp and spot fills (87-92% of the
    probed trader's fills). Only outcome fills are stored, but the page
    limit and the served cap count EVERY fill.
"""

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.traders import TraderStore

logger = logging.getLogger(__name__)

# Decision 2 (23.1): the leaderboard's share of the 1200/min REST budget.
LEADERBOARD_WEIGHT_PER_MINUTE = 500
FILLS_PAGE_LIMIT = 2000
BACKFILL_DAYS = 30  # first fetch covers the longest leaderboard window
DAY_MS = 86_400_000
HL_FILLS_SERVED_CAP = 10_000
# The served cap allows about 6 pages per pass (2000 + 1999 per page
# after the first). More means something unexpected: stop and log.
MAX_PAGES_PER_FETCH = 8
RECHECK_HOURS = 6  # re-fetch quiet traders: positions may have settled
OVERLAP_MS = 60_000  # re-read the last minute; duplicates are ignored
IDLE_SECONDS = 20.0  # when nobody is due, look again after this
BATCH_SIZE = 50  # traders taken from the queue per pass

FetchFills = Callable[[str, int, int], Awaitable[list[dict[str, Any]]]]


def fills_weight(count: int) -> int:
    """Rate-limit weight of one userFillsByTime response."""
    return 20 + math.ceil(count / 20)


def _fill_key(fill: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (fill.get("coin"), fill.get("time"), fill.get("tid"))


@dataclass(frozen=True)
class PassResult:
    """What one forward pass over [start, end] achieved."""

    complete: bool  # reached `end`
    reached: int  # every fill before this time (unix ms) is stored
    oldest: int | None  # oldest fill received (the first page's first)
    count: int  # distinct fills received, ALL coins (the served cap counts all)

    @property
    def capped(self) -> bool:
        # The pass received as many fills as Hyperliquid serves at all,
        # so older fills in the window may exist but were not served.
        return self.count >= HL_FILLS_SERVED_CAP


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
        self.due = 0  # traders due right now (the whole queue)
        self.needs_backfill = 0  # of which coverage is unknown
        # Largest number of fills one pass received. If Hyperliquid's
        # served cap is 10,000, this settles near 10,000 and never far
        # above it: a live check of the cap this code relies on.
        self.largest_pass_fills = 0
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
        self.due, self.needs_backfill = await asyncio.to_thread(
            self._store.queue_counts, stale_before
        )
        due = await asyncio.to_thread(self._store.due_traders, stale_before, BATCH_SIZE)
        for address, fills_through, coverage_from in due:
            try:
                await self._collect(address, fills_through, coverage_from)
            except Exception:
                # Logged and retried on a later pass. Marking it checked
                # moves it to the back of the queue, so a trader that
                # keeps failing cannot block the others.
                logger.exception("Fill fetch failed for %s", address)
                await asyncio.to_thread(self._store.mark_checked, address)
        return bool(due)

    async def _collect(
        self, address: str, fills_through: int | None, coverage_from: int | None
    ) -> None:
        now = int(time.time() * 1000)
        # Unknown coverage means a full 30-day backfill; otherwise only
        # what is new since the last fetch.
        if coverage_from is None or fills_through is None:
            backfill, start = True, now - BACKFILL_DAYS * DAY_MS
        else:
            backfill, start = False, fills_through - OVERLAP_MS
        result = await self._fetch_forward(address, start, now)
        self.largest_pass_fills = max(self.largest_pass_fills, result.count)

        if backfill and not result.complete:
            # An unfinished backfill (unexpected; logged) proves nothing
            # about coverage: change nothing, so it starts over next turn.
            through, coverage = fills_through, coverage_from
        else:
            # Forward paging: everything before `reached` is stored.
            through = now if result.complete else max(result.reached, start)
            if result.capped and result.oldest is not None:
                # Hyperliquid stopped serving older fills somewhere after
                # `start`: complete only from the oldest one received.
                coverage = result.oldest
            elif backfill:
                coverage = start
            else:
                coverage = coverage_from
        await asyncio.to_thread(self._store.mark_collected, address, through, coverage)
        self.traders_collected += 1
        self.last_fetch_at = time.time()

    async def _fetch_forward(self, address: str, start: int, end: int) -> PassResult:
        """Page through [start, end] oldest first, storing outcome fills.

        Each request starts at the newest fill of the previous page
        (inclusive), so no fill between pages can be skipped. A page
        shorter than FILLS_PAGE_LIMIT is the last one. The fills sharing
        that boundary millisecond come back again: they are not counted
        twice, and the database ignores them as duplicates.
        """
        cursor = start
        oldest: int | None = None
        count = 0
        boundary: set[tuple[Any, Any, Any]] = set()
        for _ in range(MAX_PAGES_PER_FETCH):
            await self._bucket.acquire(fills_weight(FILLS_PAGE_LIMIT))
            fills = await self._fetch(address, cursor, end)
            self._bucket.spend(fills_weight(len(fills)))
            self.fills_stored += await asyncio.to_thread(self._store.save_fills, address, fills)

            count += sum(1 for fill in fills if _fill_key(fill) not in boundary)
            times = [int(fill["time"]) for fill in fills if "time" in fill]
            if times and oldest is None:
                oldest = min(times)
            if len(fills) < FILLS_PAGE_LIMIT or not times:
                return PassResult(complete=True, reached=end, oldest=oldest, count=count)

            newest = max(times)
            if newest <= cursor:
                # A whole page inside one millisecond: paging cannot move on.
                logger.warning("Fill paging stuck at %d for %s", cursor, address)
                return PassResult(complete=False, reached=cursor, oldest=oldest, count=count)
            cursor = newest
            boundary = {_fill_key(fill) for fill in fills if int(fill.get("time", -1)) == newest}

        logger.warning("Fill paging for %s exceeded %d pages", address, MAX_PAGES_PER_FETCH)
        return PassResult(complete=False, reached=cursor, oldest=oldest, count=count)