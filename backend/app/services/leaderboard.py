"""Ranking outcome traders by realized PnL net of fees (Milestone 23.3).

Realized PnL can be summed per window without the opening fills,
because Hyperliquid computes each fill's closedPnl against its own
record of the entry price. Unrealized PnL (open positions) is not here.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.leaderboard import (
    Coverage,
    Leaderboard,
    LeaderboardRow,
    LeaderboardSort,
    LeaderboardWindow,
)
from app.services.traders import TraderStore

DAY_MS = 86_400_000

# Rolling spans ending now. None = All-Time: from where tracking began
# (decision 3B: the earliest stored coverage, 30-day backfill included).
WINDOW_SPANS_MS: dict[LeaderboardWindow, int | None] = {
    "24h": DAY_MS,
    "7d": 7 * DAY_MS,
    "30d": 30 * DAY_MS,
    "all": None,
}

SORT_KEYS: dict[LeaderboardSort, Callable[[LeaderboardRow], float]] = {
    "pnl": lambda row: row.net_pnl,
    "volume": lambda row: row.volume,
    "fills": lambda row: row.fills,
}


@dataclass(frozen=True)
class WindowResult:
    """Every ranked trader of one window, unsorted; cached per window."""

    generated_at: datetime
    window_start: int | None  # unix ms; None when nothing is tracked yet
    tracking_since: int | None
    traders_known: int
    traders_pending: int
    rows: list[LeaderboardRow]


def _utc(ms: int | None) -> datetime | None:
    return None if ms is None else datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def to_row(raw: dict[str, Any], window_start: int) -> LeaderboardRow:
    coverage_from: int | None = raw["coverage_from"]
    coverage: Coverage = (
        "full" if coverage_from is not None and coverage_from <= window_start else "partial"
    )
    gross = raw["gross_pnl"]
    trading = raw["trading_pnl"]
    settlement = raw["settlement_pnl"]
    return LeaderboardRow(
        address=raw["address"],
        net_pnl=gross - raw["fees"],
        gross_pnl=gross,
        trading_pnl=trading,
        settlement_pnl=settlement,
        # The remainder, so the three parts always add up to gross.
        conversion_pnl=gross - trading - settlement,
        fees=raw["fees"],
        volume=raw["volume"],
        fills=raw["fills"],
        markets=raw["markets"],
        settlements_won=raw["won"],
        settlements_lost=raw["lost"],
        settlements_fractional=raw["fractional"],
        coverage=coverage,
        coverage_from=_utc(coverage_from),
        fills_through=_utc(raw["fills_through"]),
        behind=raw["last_trade_at"] > raw["fills_through"],
    )


def compute_window(store: TraderStore, window: LeaderboardWindow) -> WindowResult:
    """Blocking (SQLite): call through asyncio.to_thread."""
    generated_at = datetime.now(timezone.utc)
    now_ms = int(generated_at.timestamp() * 1000)
    span = WINDOW_SPANS_MS[window]
    data = store.leaderboard(None if span is None else now_ms - span)
    start = data.start_ms if data.start_ms is not None else 0
    return WindowResult(
        generated_at=generated_at,
        window_start=data.start_ms,
        tracking_since=data.tracking_since,
        traders_known=data.traders_known,
        traders_pending=data.traders_pending,
        rows=[to_row(raw, start) for raw in data.rows],
    )


def rank(rows: list[LeaderboardRow], sort: LeaderboardSort, limit: int) -> list[LeaderboardRow]:
    """Best first by the chosen measure; ties ordered by address.

    Python's sort is stable: sorting by address first, then by the
    measure, keeps equal measures in address order, so the order never
    flickers between requests.
    """
    ordered = sorted(rows, key=lambda row: row.address)
    ordered.sort(key=SORT_KEYS[sort], reverse=True)
    return ordered[:limit]


def build_leaderboard(
    result: WindowResult, window: LeaderboardWindow, sort: LeaderboardSort, limit: int
) -> Leaderboard:
    return Leaderboard(
        window=window,
        sort=sort,
        window_start=_utc(result.window_start),
        tracking_since=_utc(result.tracking_since),
        generated_at=result.generated_at,
        traders_known=result.traders_known,
        traders_pending=result.traders_pending,
        traders_ranked=len(result.rows),
        rows=rank(result.rows, sort, limit),
    )