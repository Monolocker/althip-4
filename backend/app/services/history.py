"""Record of market history (Milestone 21)

Hyperliquid deletes market's candles when it settles (M19).
To view a market after it has settled, said market has to be 
recorded while live. This module owns SQLite db and the background
task that samples every live market / 5 min. 
"""

import asyncio
import logging
import sqlite3
import time
from collections.abc import Awaitable, Callable
from contextlib import closing 
from datetime import datetime, timezone
from pathlib import Path

from app.models.market import OutcomeMarket

logger = logging.getLogger(__name__)

# backend/data/history.sqlite3 (this file is backend/app/services/history.py)
# backend/data/ is in .gitignore: the database is data, not code
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "history.sqlite3"

# Decision 1 (21): one sample per market every 5 min
SAMPLE_INTERVAL_SECONDS = 300

SCHEMA = """
CREATE TABLE IF NOT EXISTS markets (
    id             TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    name           TEXT NOT NULL,
    description    TEXT NOT NULL,
    venue          TEXT NOT NULL,
    category       TEXT,
    question_id    TEXT,
    question_title TEXT,
    outcome_label  TEXT,
    event_at       TEXT,
    resolves_by    TEXT,
    first_seen     TEXT NOT NULL,
    last_seen      TEXT NOT NULL
);

-- One row per market per 5-minute slot. The primary key (market, time)
-- makes re-recording the same slot harmless, and WITHOUT ROWID stores
-- rows in key order, so one market's history is read as one
-- contiguous range.
CREATE TABLE IF NOT EXISTS observations (
    market_id   TEXT    NOT NULL REFERENCES markets(id),
    observed_at INTEGER NOT NULL,  -- unix seconds, start of the slot (UTC)
    price       REAL,              -- side-0 mid
    bid         REAL,              -- side-0 best bid (from the sweep)
    ask         REAL,              -- side-0 best ask (from the sweep)
    quality     TEXT,              -- tight / wide / unreliable / NULL
    volume_24h  REAL,
    PRIMARY KEY (market_id, observed_at)
) WITHOUT ROWID;
"""

# Upsert: insert a new market, or refresh an existing one in place.
# first_seen is deliberately NOT in the update list: it keeps the value
# from the very first time we saw the market.
UPSERT_MARKET = """
INSERT INTO markets (
    id, title, name, description, venue, category, question_id,
    question_title, outcome_label, event_at, resolves_by,
    first_seen, last_seen
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    title = excluded.title,
    name = excluded.name,
    description = excluded.description,
    venue = excluded.venue,
    category = excluded.category,
    question_id = excluded.question_id,
    question_title = excluded.question_title,
    outcome_label = excluded.outcome_label,
    event_at = excluded.event_at,
    resolves_by = excluded.resolves_by,
    last_seen = excluded.last_seen
"""

INSERT_OBSERVATION = """
INSERT OR IGNORE INTO observations (
    market_id, observed_at, price, bid, ask, quality, volume_24h
) VALUES (?, ?, ?, ?, ?, ?, ?)
"""


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


class HistoryStore:
    """All SQL lives here; the rest of the app calls plain methods."""

    def __init__(self, path: Path = DEFAULT_DB_PATH) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        """Create the folder, the tables, and switch on WAL mode.

        WAL (write-ahead logging) lets readers keep reading while the
        recorder writes. The setting is stored in the database file, so
        it only needs to be set once, but setting it again is harmless.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA)

    def record(self, markets: list[OutcomeMarket], observed_at: int) -> int:
        """Upsert every market and add one observation each, in one transaction.

        Returns the number of observations actually inserted (0 for a
        slot that was already recorded).
        """
        seen_at = datetime.fromtimestamp(observed_at, tz=timezone.utc).isoformat()
        market_rows = [
            (
                m.id,
                m.question,
                m.name,
                m.description,
                m.venue,
                m.category,
                m.parent.id if m.parent else None,
                m.parent.title if m.parent else None,
                m.parent.outcome_label if m.parent else None,
                _iso(m.event_at),
                _iso(m.resolves_by),
                seen_at,
                seen_at,
            )
            for m in markets
        ]
        observation_rows = [
            (
                m.id,
                observed_at,
                m.sides[0].price if m.sides else None,
                m.book.bid if m.book else None,
                m.book.ask if m.book else None,
                m.book.quality if m.book else None,
                m.volume_24h,
            )
            for m in markets
        ]
        # `closing` closes the connection afterwards; `with connection`
        # wraps the writes in ONE transaction: all of them commit, or on
        # any error none do.
        with closing(self._connect()) as connection, connection:
            connection.executemany(UPSERT_MARKET, market_rows)
            before = connection.total_changes
            connection.executemany(INSERT_OBSERVATION, observation_rows)
            return connection.total_changes - before

    def file_size(self) -> int:
        """Bytes on disk: the database plus its write-ahead log.

        In WAL mode, recent writes sit in "history.sqlite3-wal" until
        SQLite copies them into the main file (a "checkpoint"), so the
        main file alone would under-report.
        """
        total = 0
        for path in (self.path, self.path.with_name(self.path.name + "-wal")):
            try:
                total += path.stat().st_size
            except FileNotFoundError:
                pass
        return total


class HistoryRecorder:
    """Samples every live market once per 5-minute slot, forever."""

    def __init__(
        self,
        store: HistoryStore,
        markets_source: Callable[[], Awaitable[list[OutcomeMarket]]],
        interval: int = SAMPLE_INTERVAL_SECONDS,
    ) -> None:
        self._store = store
        self._markets_source = markets_source
        self._interval = interval
        self.last_recorded_at: int | None = None  # slot start, unix seconds
        self.last_batch: int = 0  # observations written in the last slot
        self.slots_recorded: int = 0  # since this process started

    def current_slot(self) -> int:
        """Start of the current 5-minute slot, e.g. 12:35:00 for 12:37:41.

        Aligning samples to fixed slots means a restart inside a slot
        rewrites the same rows (ignored by the primary key) instead of
        creating near-duplicate samples a few seconds apart.
        """
        now = int(time.time())
        return now - now % self._interval

    async def run_forever(self) -> None:
        """Record, then sleep until the next slot. One failure must not end it.

        Like the book sweep (18.3b): `except Exception` never swallows
        asyncio.CancelledError, so shutdown still stops this task.
        """
        while True:
            try:
                await self._record_once()
            except Exception:
                logger.exception("History recording failed; will retry next slot")
            seconds_left = self._interval - time.time() % self._interval
            await asyncio.sleep(seconds_left)

    async def _record_once(self) -> None:
        markets = await self._markets_source()
        slot = self.current_slot()
        inserted = await asyncio.to_thread(self._store.record, markets, slot)
        self.last_recorded_at = slot
        self.last_batch = inserted
        self.slots_recorded += 1