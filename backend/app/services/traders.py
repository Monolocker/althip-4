"""Outcome traders and their fills (Milestone 23).

Hyperliquid has no "list of outcome traders", but every public trade
names its buyer and seller (the 23 probe: trades carry "users"). The
trade watcher (23.1) stores the addresses seen; the fill collector
(23.2) stores their outcome fills. Same SQLite file as the history
recorder.
"""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.history import DEFAULT_DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS traders (
    address       TEXT PRIMARY KEY,
    first_seen    TEXT    NOT NULL,  -- when THIS APP first saw them trade
    last_trade_at INTEGER NOT NULL,  -- their latest trade seen, unix ms
    trades_seen   INTEGER NOT NULL   -- outcome trades seen by this app
);

-- One row per outcome fill (23.2). closed_pnl is BEFORE fees (23 probe),
-- so a trader's net realized PnL is SUM(closed_pnl) - SUM(fee). The key
-- includes coin and time because merges and settlements are fills
-- whose trade ids are not guaranteed unique per address.
CREATE TABLE IF NOT EXISTS trader_fills (
    address    TEXT    NOT NULL,
    coin       TEXT    NOT NULL,
    time       INTEGER NOT NULL,  -- unix ms
    tid        INTEGER NOT NULL,
    dir        TEXT    NOT NULL,  -- Buy, Sell, Settlement, Merge Outcome, ...
    px         REAL    NOT NULL,
    sz         REAL    NOT NULL,
    closed_pnl REAL    NOT NULL,
    fee        REAL    NOT NULL,
    fee_token  TEXT    NOT NULL,
    PRIMARY KEY (address, coin, time, tid)
) WITHOUT ROWID;

-- The leaderboard (23.3) sums fills by time window.
CREATE INDEX IF NOT EXISTS trader_fills_by_time ON trader_fills (time);

-- Named one-time data migrations (23.2b), recorded so each runs once.
-- A table rather than PRAGMA user_version: this SQLite file is shared
-- by several stores, and names cannot collide the way one number can.
CREATE TABLE IF NOT EXISTS migrations (
    name       TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""

# Columns added to `traders` in 23.2. CREATE TABLE IF NOT EXISTS never
# changes an existing table, so they are added by a small migration.
TRADER_COLUMNS_23_2 = {
    # All fills up to this time (unix ms) are stored.
    "fills_through": "INTEGER",
    # Earliest time from which this trader's fills are complete. Later
    # than the 30-day backfill start when Hyperliquid no longer served
    # their older fills (only the most recent ones are available).
    # NULL = unknown: the trader needs a (re)backfill (23.2b).
    "coverage_from": "INTEGER",
    # When the collector last fetched this trader (ISO, UTC).
    "fills_checked_at": "TEXT",
}

UPSERT_TRADER = """
INSERT INTO traders (address, first_seen, last_trade_at, trades_seen)
VALUES (?, ?, ?, ?)
ON CONFLICT(address) DO UPDATE SET
    last_trade_at = MAX(last_trade_at, excluded.last_trade_at),
    trades_seen = trades_seen + excluded.trades_seen
"""

INSERT_FILL = """
INSERT OR IGNORE INTO trader_fills (
    address, coin, time, tid, dir, px, sz, closed_pnl, fee, fee_token
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# 23.2b repair: fills collected before the 23.2b fix may have silent
# gaps (a full page of perp/spot fills stored nothing and was taken as
# "already stored"). Those gaps cannot be detected, so every trader's
# coverage becomes unknown, which queues a fresh backfill for each.
# Stored fills are kept: re-fetched ones are ignored as duplicates.
REPAIR_23_2B = "23.2b-rebackfill-all"

# Traders whose fills need fetching: coverage unknown (never fetched, or
# reset by a repair), traded since the last fetch, or not checked for a
# while (positions can SETTLE without the trader trading, and settlement
# is not in the trade stream).
DUE_CONDITION = """
    coverage_from IS NULL
    OR fills_through IS NULL
    OR last_trade_at > fills_through
    OR fills_checked_at IS NULL
    OR fills_checked_at < :stale_before
"""

# Fair order (23.2b): never checked first, then the least recently
# checked, so every due trader is reached within one cycle. Ordering by
# activity starved everyone below the batch limit (23.3, section J).
DUE_TRADERS = f"""
SELECT address, fills_through, coverage_from FROM traders
WHERE {DUE_CONDITION}
ORDER BY fills_checked_at IS NOT NULL, fills_checked_at
LIMIT :limit
"""

# For /health: the real queue length, and how many still need a backfill.
QUEUE_COUNTS = f"""
SELECT COUNT(*), COALESCE(SUM(coverage_from IS NULL), 0)
FROM traders WHERE {DUE_CONDITION}
"""

# Leaderboard (23.3). Evidence from the 23.3a probe:
#   - every stored fee is USDC (1,875,783 of 1,875,783 fills), so
#     closed_pnl - fee is a valid USDC subtraction;
#   - Merge/Split Outcome fills always carry px 0.5 (a fixed conversion
#     value, not a traded price), so volume counts Buy / Sell only;
#   - settlements are px 1 (won, all PnL > 0) or px 0 (lost, all PnL < 0),
#     apart from rare fractional payouts (2 fills at px 0.5).
# Only FETCHED traders are ranked: fills_through IS NULL means the first
# fetch has not finished, so their stored fills may be half a backfill.
TRADER_SUMMARY = """
SELECT COUNT(*), COALESCE(SUM(fills_through IS NULL), 0), MIN(coverage_from)
FROM traders
"""

LEADERBOARD = """
WITH f AS (
    SELECT address,
        SUM(closed_pnl) AS gross_pnl,
        SUM(CASE WHEN dir IN ('Buy', 'Sell') THEN closed_pnl ELSE 0 END) AS trading_pnl,
        SUM(CASE WHEN dir = 'Settlement' THEN closed_pnl ELSE 0 END) AS settlement_pnl,
        SUM(fee) AS fees,
        SUM(CASE WHEN dir IN ('Buy', 'Sell') THEN px * sz ELSE 0 END) AS volume,
        COUNT(*) AS fills,
        -- coin "#{10*N+s}": outcome N is the number divided by 10
        COUNT(DISTINCT CAST(substr(coin, 2) AS INTEGER) / 10) AS markets,
        SUM(dir = 'Settlement' AND px = 1) AS won,
        SUM(dir = 'Settlement' AND px = 0) AS lost,
        SUM(dir = 'Settlement' AND px > 0 AND px < 1) AS fractional
    FROM trader_fills
    WHERE time >= :start
    GROUP BY address
)
SELECT f.*, t.coverage_from, t.fills_through, t.last_trade_at
FROM f JOIN traders t USING (address)
WHERE t.fills_through IS NOT NULL
"""


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class LeaderboardData:
    start_ms: int | None  # window start used; None when nothing is tracked yet
    tracking_since: int | None  # earliest coverage_from of any trader
    traders_known: int
    traders_pending: int  # discovered but never fetched
    rows: list[dict[str, Any]]  # one per fetched trader with fills in the window


class TraderStore:
    def __init__(self, path: Path = DEFAULT_DB_PATH) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)
            # Migration: add any 23.2 column the table does not have yet.
            existing = {row[1] for row in connection.execute("PRAGMA table_info(traders)")}
            for column, declaration in TRADER_COLUMNS_23_2.items():
                if column not in existing:
                    connection.execute(f"ALTER TABLE traders ADD COLUMN {column} {declaration}")
            connection.commit()
            # The repair and its record commit together, or not at all.
            with connection:
                applied = connection.execute(
                    "SELECT 1 FROM migrations WHERE name = ?", (REPAIR_23_2B,)
                ).fetchone()
                if applied is None:
                    connection.execute("UPDATE traders SET coverage_from = NULL")
                    connection.execute(
                        "INSERT INTO migrations (name, applied_at) VALUES (?, ?)",
                        (REPAIR_23_2B, datetime.now(timezone.utc).isoformat()),
                    )

    def record(self, activity: dict[str, tuple[int, int]]) -> None:
        """Save a batch: address -> (latest trade time ms, trades in batch)."""
        if not activity:
            return
        now = datetime.now(timezone.utc).isoformat()
        rows = [(address, now, last, count) for address, (last, count) in activity.items()]
        with closing(self._connect()) as connection, connection:
            connection.executemany(UPSERT_TRADER, rows)

    def count(self) -> int:
        with closing(self._connect()) as connection:
            return connection.execute("SELECT COUNT(*) FROM traders").fetchone()[0]

    def due_traders(
        self, stale_before: datetime, limit: int
    ) -> list[tuple[str, int | None, int | None]]:
        """(address, fills_through, coverage_from) of the next traders to fetch."""
        with closing(self._connect()) as connection:
            return connection.execute(
                DUE_TRADERS, {"stale_before": stale_before.isoformat(), "limit": limit}
            ).fetchall()

    def queue_counts(self, stale_before: datetime) -> tuple[int, int]:
        """(traders due, of which needing a backfill)."""
        with closing(self._connect()) as connection:
            due, backfill = connection.execute(
                QUEUE_COUNTS, {"stale_before": stale_before.isoformat()}
            ).fetchone()
            return due, backfill

    def save_fills(self, address: str, fills: list[dict[str, Any]]) -> int:
        """Store a page of fills (outcome coins only); returns rows added."""
        rows = [
            (
                address,
                str(f["coin"]),
                int(f["time"]),
                int(f.get("tid") or 0),
                str(f.get("dir") or ""),
                _float(f.get("px")),
                _float(f.get("sz")),
                _float(f.get("closedPnl")),
                _float(f.get("fee")),
                str(f.get("feeToken") or ""),
            )
            for f in fills
            if str(f.get("coin", "")).startswith("#") and "time" in f
        ]
        with closing(self._connect()) as connection, connection:
            before = connection.total_changes
            connection.executemany(INSERT_FILL, rows)
            return connection.total_changes - before

    def mark_collected(
        self, address: str, fills_through: int | None, coverage_from: int | None
    ) -> None:
        """Record a fetch: both values are written as given (the collector
        decides them), and the trader moves to the back of the queue."""
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE traders SET fills_through = ?, coverage_from = ?, "
                "fills_checked_at = ? WHERE address = ?",
                (fills_through, coverage_from, datetime.now(timezone.utc).isoformat(), address),
            )

    def mark_checked(self, address: str) -> None:
        """A failed fetch: change nothing but the queue position, so a
        trader that keeps failing cannot block the others."""
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE traders SET fills_checked_at = ? WHERE address = ?",
                (datetime.now(timezone.utc).isoformat(), address),
            )

    def fill_count(self) -> int:
        with closing(self._connect()) as connection:
            return connection.execute("SELECT COUNT(*) FROM trader_fills").fetchone()[0]

    def leaderboard(self, start_ms: int | None) -> LeaderboardData:
        """Per-trader totals for fills at or after start_ms.

        start_ms None = All-Time, which starts at tracking_since.
        """
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            known, pending, since = connection.execute(TRADER_SUMMARY).fetchone()
            start = start_ms if start_ms is not None else since
            rows = (
                [dict(row) for row in connection.execute(LEADERBOARD, {"start": start})]
                if start is not None
                else []
            )
        return LeaderboardData(start, since, known, pending, rows)