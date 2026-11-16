"""Domain models for the trader leaderboard (Milestone 23.3, v2 in 26.1)"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

# Rolling windows ending now; "all" = each trader's whole stored history
LeaderboardWindow = Literal["24h", "7d", "30d", "all"]


class LeaderboardRow(BaseModel):
    """One trader's realized results inside one window. Money in USDC.

    Only traders whose stored fills are complete for the window get a
    row (decision, 26.1), so no row needs a coverage flag.
    """

    model_config = ConfigDict(populate_by_name=True)

    address: str
    net_pnl: float = Field(alias="netPnl")  # gross_pnl - fees: the ranking measure
    gross_pnl: float = Field(alias="grossPnl")  # sum of closedPnl (before fees)
    # Where gross_pnl came from; the three always add up to it.
    trading_pnl: float = Field(alias="tradingPnl")  # Buy / Sell fills
    settlement_pnl: float = Field(alias="settlementPnl")  # Settlement fills
    conversion_pnl: float = Field(alias="conversionPnl")  # merges, splits, negations
    fees: float
    volume: float  # USDC notional of Buy / Sell fills only
    markets: int  # distinct outcomes (both sides of a market count once)
    # Per market (decision, 26.1): a market with something realized in
    # the window is a win if its net PnL is above 0, a loss if below.
    wins: int
    losses: int


class Leaderboard(BaseModel):
    """Traders ranked by net realized PnL within one window"""

    model_config = ConfigDict(populate_by_name=True)

    window: LeaderboardWindow
    # None for All-Time: every trader counts from their own history start
    window_start: datetime | None = Field(alias="windowStart")
    generated_at: datetime = Field(alias="generatedAt")
    traders_known: int = Field(alias="tradersKnown")  # discovered by the trade stream
    traders_pending: int = Field(alias="tradersPending")  # discovered, never fetched
    traders_ranked: int = Field(alias="tradersRanked")  # complete, with fills in window
    # Left out because their stored fills do not cover this window yet
    # (pending traders included).
    traders_excluded: int = Field(alias="tradersExcluded")
    rows: list[LeaderboardRow]  # best first; the first 'limit' only