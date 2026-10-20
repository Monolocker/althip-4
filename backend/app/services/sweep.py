"""Background sweep of every live market's order book (Milestone 18.3b).

Fetches the side-0 book of each market one at a time, spread evenly over
SWEEP_INTERVAL_SECONDS, and keeps the best bid and ask per coin. The
normalizer turns those into a tight / wide / unreliable label.

Sweep data is minutes old by design. It answers "is there a real market
here?" for list display only, and must NEVER feed an order decision:
trading reads the live book.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from app.services.hyperliquid import HyperliquidClient, HyperliquidError
from app.services.normalize import TopOfBook, normalize_order_book

logger = logging.getLogger(__name__)

# One full pass over every market. Cost: 2 weight per l2Book request, so
# ~335 markets cost ~670 weight per sweep, ~220 weight/min at 180s.
# Running several backend worker processes would multiply this, because
# each process runs its own sweep.
SWEEP_INTERVAL_SECONDS = 180.0

# After an unexpected error, wait this long before starting a new sweep.
RETRY_DELAY_SECONDS = 30.0


class BookSweeper:
    """Owns the sweep loop and its results.

    The rest of the app only reads `tops`, `last_completed_at` and
    `last_failures`; how the data is gathered (polling today, perhaps a
    WebSocket feed later) stays inside this class.
    """

    def __init__(
        self,
        client: HyperliquidClient,
        coins_source: Callable[[], Awaitable[list[str]]],
        interval: float = SWEEP_INTERVAL_SECONDS,
    ) -> None:
        self._client = client
        self._coins_source = coins_source
        self._interval = interval
        self.tops: dict[str, TopOfBook] = {}
        self.last_completed_at: float | None = None
        self.last_failures = 0

    async def run_forever(self) -> None:
        """Sweep until cancelled. One bad sweep must not end the loop.

        asyncio.CancelledError derives from BaseException, not Exception,
        so `except Exception` below never swallows a cancellation: shutdown
        still stops this task.
        """
        while True:
            try:
                await self._sweep_once()
            except Exception:
                logger.exception("Book sweep failed; retrying shortly")
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    async def _sweep_once(self) -> None:
        coins = await self._coins_source()
        if not coins:
            await asyncio.sleep(self._interval)
            return

        # Pacing: spread requests evenly instead of bursting them, so the
        # rate-limit cost is a steady trickle rather than a spike.
        delay = self._interval / len(coins)
        failures = 0
        for coin in coins:
            try:
                raw = await self._client.fetch_l2_book(coin)
                book = normalize_order_book(raw, side_index=0)
                self.tops[coin] = TopOfBook(
                    bid=book.best_bid, ask=book.best_ask, checked_at=time.time()
                )
            except HyperliquidError as exc:
                # One failed book is not worth a stack trace; the previous
                # entry (if any) ages out via TOP_MAX_AGE_SECONDS.
                failures += 1
                logger.debug("Book sweep: %s failed: %s", coin, exc)
            await asyncio.sleep(delay)

        # Forget markets that are no longer listed (settled or removed).
        live = set(coins)
        for coin in [c for c in self.tops if c not in live]:
            del self.tops[coin]

        self.last_completed_at = time.time()
        self.last_failures = failures
        logger.info(
            "Book sweep complete: %d coins, %d failures", len(coins), failures
        )