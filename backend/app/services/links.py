"""Curated links between Hyperliquid outcomes and other venues (22.2).

A link exists only because a person confirmed it: the 22 probes showed
automatic matching pairs the wrong markets (an FOMC search returned a
2024 Belgian election). The links live in the same SQLite file as the
history recorder, in their own table.
"""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.models.venue import LinkGroupCreate, VenueLink
from app.services.history import DEFAULT_DB_PATH

# CHECK constraints make the database itself enforce the rules, so no
# code path (or a typo in a future one) can store an invalid link:
#   - match_level is one of the two levels (decision 2)
#   - a "comparable" link must say how the venues differ
# UNIQUE (market_id, venue): one link per outcome per venue.
SCHEMA = """
CREATE TABLE IF NOT EXISTS venue_links (
    id          INTEGER PRIMARY KEY,
    market_id   TEXT NOT NULL,
    venue       TEXT NOT NULL CHECK (venue IN ('polymarket', 'kalshi')),
    external_id TEXT NOT NULL,
    match_level TEXT NOT NULL CHECK (match_level IN ('identical', 'comparable')),
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    UNIQUE (market_id, venue),
    CHECK (match_level = 'identical' OR length(trim(note)) > 0)
);
"""

COLUMNS = "id, market_id, venue, external_id, match_level, note, created_at"


class DuplicateLinkError(Exception):
    """An outcome already has a link to that venue."""


def _row_to_link(row: tuple) -> VenueLink:
    id_, market_id, venue, external_id, match_level, note, created_at = row
    return VenueLink(
        id=id_,
        market_id=market_id,
        venue=venue,
        external_id=external_id,
        match_level=match_level,
        note=note,
        created_at=datetime.fromisoformat(created_at),
    )


class LinkStore:
    def __init__(self, path: Path = DEFAULT_DB_PATH) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)

    def create_group(self, group: LinkGroupCreate) -> list[VenueLink]:
        """Insert every link of a confirmed match in ONE transaction:
        either the whole match is linked, or (on any error) none of it."""
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            with closing(self._connect()) as connection, connection:
                ids = []
                for target in group.links:
                    cursor = connection.execute(
                        "INSERT INTO venue_links (market_id, venue, external_id, "
                        "match_level, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            target.market_id,
                            group.venue,
                            target.external_id,
                            group.match_level,
                            group.note.strip(),
                            created_at,
                        ),
                    )
                    ids.append(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            # The UNIQUE or a CHECK constraint refused the row.
            raise DuplicateLinkError(str(exc)) from exc
        return [link for link in self.links_for_ids(ids)]

    def links_for_ids(self, ids: list[int]) -> list[VenueLink]:
        if not ids:
            return []
        placeholders = ", ".join("?" for _ in ids)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT {COLUMNS} FROM venue_links WHERE id IN ({placeholders}) ORDER BY id",
                ids,
            ).fetchall()
        return [_row_to_link(row) for row in rows]

    def links_for_market(self, market_id: str) -> list[VenueLink]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT {COLUMNS} FROM venue_links WHERE market_id = ? ORDER BY venue",
                (market_id,),
            ).fetchall()
        return [_row_to_link(row) for row in rows]

    def delete(self, link_id: int) -> bool:
        """Remove one link; False if it did not exist."""
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute("DELETE FROM venue_links WHERE id = ?", (link_id,))
            return cursor.rowcount > 0