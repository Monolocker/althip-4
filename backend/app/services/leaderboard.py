"""Ranking outcome traders by realized PnL net of fees (23.3, v2 in 26.1).

Realized PnL can be summed per window without the opening fills,
because Hyperliquid computes each fill's closedPnl against its own
record of the entry price. Unrealized PnL (open positions) is not here.

v2 (26.1): ranked by net PnL only, and a trader is ranked only when
their stored fills are complete for the window; the others are counted
as excluded instead of being shown with a flag.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.leaderboard import Leaderboard, LeaderboardRow, LeaderboardWindow
from app.services.traders import TraderStore

DAY_MS = 86_400_000

# Rolling spans ending now. None = All-Time: each trader from the start
# of their own complete history (decision, 26.1).
WINDOW_SPANS_MS: dict[LeaderboardWindow, int | None] = {
    "24h": DAY_MS,
    "7d": 7 * DAY_MS,
    "30d": 30 * DAY_MS,
    "all": None,
}

# A trader still counts as complete if their fills are fetched to within
# this long of their latest trade seen on the trade stream. An active
# trader is always a little behind between two collector visits, and
# excluding them for minutes at a time would make the board flicker.
# Assumption (26.1): one hour; the verification measures the real lags.
LAG_TOLERANCE_MS = 60 * 60 * 1000


@dataclass(frozen=True)
class WindowResult:
    """Every ranked trader of one window, unsorted; cached per window."""

    generated_at: datetime
    window_start: int | None  # unix ms; None for All-Time
    traders_known: int
    traders_pending: int
    traders_complete: int
    rows: list[LeaderboardRow]


def _utc(ms: int | None) -> datetime | None:
    return None if ms is None else datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def to_row(raw: dict[str, Any]) -> LeaderboardRow:
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
        markets=raw["markets"],
        wins=raw["wins"],
        losses=raw["losses"],
    )


def compute_window(store: TraderStore, window: LeaderboardWindow) -> WindowResult:
    """Blocking (SQLite): call through asyncio.to_thread."""
    generated_at = datetime.now(timezone.utc)
    now_ms = int(generated_at.timestamp() * 1000)
    span = WINDOW_SPANS_MS[window]
    start = None if span is None else now_ms - span
    data = store.leaderboard(start, LAG_TOLERANCE_MS)
    return WindowResult(
        generated_at=generated_at,
        window_start=start,
        traders_known=data.traders_known,
        traders_pending=data.traders_pending,
        traders_complete=data.traders_complete,
        rows=[to_row(raw) for raw in data.rows],
    )


def rank(rows: list[LeaderboardRow], limit: int) -> list[LeaderboardRow]:
    """Best net PnL first; ties ordered by address.

    Python's sort is stable: sorting by address first, then by PnL,
    keeps equal PnL in address order, so the order never flickers
    between requests.
    """
    ordered = sorted(rows, key=lambda row: row.address)
    ordered.sort(key=lambda row: row.net_pnl, reverse=True)
    return ordered[:limit]


def build_leaderboard(result: WindowResult, window: LeaderboardWindow, limit: int) -> Leaderboard:
    return Leaderboard(
        window=window,
        window_start=_utc(result.window_start),
        generated_at=result.generated_at,
        traders_known=result.traders_known,
        traders_pending=result.traders_pending,
        traders_ranked=len(result.rows),
        traders_excluded=result.traders_known - result.traders_complete,
        rows=rank(result.rows, limit),
    )