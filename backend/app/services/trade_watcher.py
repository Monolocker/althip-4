"""Discovering outcome traders from Hyperliquid's live trade stream (23.1).

Subscribes to the WebSocket "trades" channel of every live outcome coin.
Each trade names its two counterparties ("users": [buyer, seller]), so
watching trades reveals who trades outcomes, at no REST rate-limit cost.

Documented limits (Hyperliquid rate-limit docs): at most 1000 WebSocket
subscriptions and 2000 messages sent per minute per IP. Observed: the
server closes idle connections, so a ping is sent regularly.
"""

import asyncio
import json
import logging
import random
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidURI

from app.services.traders import TraderStore

logger = logging.getLogger(__name__)

WS_URL = "wss://api.hyperliquid.xyz/ws"

# Below the documented 1000 subscriptions per IP, leaving room for the
# frontend's own order-book socket from the same machine.
MAX_SUBSCRIPTIONS = 900
PING_SECONDS = 30.0  # keep the connection from being closed as idle
FLUSH_SECONDS = 15.0  # write discovered traders to the database this often
RESYNC_SECONDS = 300.0  # re-check which coins are live this often
SEEN_TRADES_LIMIT = 50_000  # remember this many trade ids for de-duplication
SUBSCRIBE_PAUSE = 0.01  # pace subscribe messages (2000 per minute allowed)


class TradeWatcher:
    """One WebSocket connection, reconnecting forever with backoff."""

    def __init__(
        self,
        store: TraderStore,
        coins_source: Callable[[], Awaitable[list[str]]],
        url: str = WS_URL,
    ) -> None:
        self._store = store
        self._coins_source = coins_source
        self._url = url
        # address -> (latest trade ms, trades) since the last flush
        self._pending: dict[str, tuple[int, int]] = {}
        # trade id -> None, oldest first: an ordered set with a size cap.
        self._seen_tids: OrderedDict[int, None] = OrderedDict()
        self.connected = False
        self.subscriptions = 0
        self.trades_seen = 0
        self.traders_known = 0
        self.last_trade_at: float | None = None  # unix seconds

    async def run_forever(self) -> None:
        attempt = 0
        while True:
            try:
                await self._session()
                attempt = 0  # a clean session resets the backoff
            except (ConnectionClosed, InvalidHandshake, InvalidURI, OSError) as exc:
                logger.warning("Trade stream disconnected: %s", exc)
            except Exception:
                logger.exception("Trade watcher failed; reconnecting")
            finally:
                self.connected = False
                self.subscriptions = 0
                await self._flush()
            attempt += 1
            # Jittered exponential backoff (as in the frontend's hlSocket, M15).
            delay = min(60.0, 2 ** min(attempt, 6)) * random.uniform(0.5, 1.0)
            await asyncio.sleep(delay)

    async def _session(self) -> None:
        async with connect(self._url, ping_interval=None, max_size=2**22) as ws:
            self.connected = True
            subscribed: set[str] = set()
            await self._sync_subscriptions(ws, subscribed)
            next_ping = time.monotonic() + PING_SECONDS
            next_flush = time.monotonic() + FLUSH_SECONDS
            next_resync = time.monotonic() + RESYNC_SECONDS

            while True:
                now = time.monotonic()
                timeout = max(0.1, min(next_ping, next_flush, next_resync) - now)
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    self._handle(raw)
                except asyncio.TimeoutError:
                    pass  # time for housekeeping, not an error

                now = time.monotonic()
                if now >= next_ping:
                    await ws.send(json.dumps({"method": "ping"}))
                    next_ping = now + PING_SECONDS
                if now >= next_flush:
                    await self._flush()
                    next_flush = now + FLUSH_SECONDS
                if now >= next_resync:
                    await self._sync_subscriptions(ws, subscribed)
                    next_resync = now + RESYNC_SECONDS

    async def _sync_subscriptions(self, ws: Any, subscribed: set[str]) -> None:
        """Subscribe to newly live coins, unsubscribe from ones now gone."""
        wanted = set((await self._coins_source())[:MAX_SUBSCRIPTIONS])
        for method, coins in (("unsubscribe", subscribed - wanted), ("subscribe", wanted - subscribed)):
            for coin in sorted(coins):
                await ws.send(json.dumps({
                    "method": method,
                    "subscription": {"type": "trades", "coin": coin},
                }))
                await asyncio.sleep(SUBSCRIBE_PAUSE)
        subscribed.clear()
        subscribed.update(wanted)
        self.subscriptions = len(subscribed)

    def _handle(self, raw: str | bytes) -> None:
        try:
            message = json.loads(raw)
        except ValueError:
            return
        if not isinstance(message, dict) or message.get("channel") != "trades":
            return  # pong, subscriptionResponse, ...
        for trade in message.get("data") or []:
            self._record_trade(trade)

    def _record_trade(self, trade: Any) -> None:
        if not isinstance(trade, dict):
            return
        tid = trade.get("tid")
        if tid is not None:
            # The same trade may arrive on both sides' coins; count it once.
            if tid in self._seen_tids:
                return
            self._seen_tids[tid] = None
            if len(self._seen_tids) > SEEN_TRADES_LIMIT:
                self._seen_tids.popitem(last=False)  # forget the oldest
        when = int(trade.get("time") or 0)
        for address in trade.get("users") or []:
            if isinstance(address, str) and address.startswith("0x"):
                last, count = self._pending.get(address, (0, 0))
                self._pending[address] = (max(last, when), count + 1)
        self.trades_seen += 1
        self.last_trade_at = when / 1000 if when else time.time()

    async def _flush(self) -> None:
        """Write the batch since the last flush in one transaction."""
        batch, self._pending = self._pending, {}
        if batch:
            await asyncio.to_thread(self._store.record, batch)
            self.traders_known = await asyncio.to_thread(self._store.count)