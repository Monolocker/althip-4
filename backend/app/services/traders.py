"""Outcome traders discovered from the public trade stream (Milestone 23).

Hyperliquid has no "list of outcome traders", but every public trade
names its buyer and seller (the 23 probe: trades carry "users"). This
module stores the addresses seen, in the same SQLite file as the
history recorder. 23.2 will add their fills next to them.
"""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.services.history import DEFAULT_DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS traders (
    address       TEXT PRIMARY KEY,
    first_seen    TEXT    NOT NULL,  -- when THIS APP first saw them trade
    last_trade_at INTEGER NOT NULL,  -- their latest trade seen, unix ms
    trades_seen   INTEGER NOT NULL   -- outcome trades seen by this app
);
"""

# One row per address; a later batch only moves last_trade_at forward
# and adds to the count. first_seen keeps its first value (as in 21.1).
UPSERT_TRADER = """
INSERT INTO traders (address, first_seen, last_trade_at, trades_seen)
VALUES (?, ?, ?, ?)
ON CONFLICT(address) DO UPDATE SET
    last_trade_at = MAX(last_trade_at, excluded.last_trade_at),
    trades_seen = trades_seen + excluded.trades_seen
"""


class TraderStore:
    def __init__(self, path: Path = DEFAULT_DB_PATH) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)

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