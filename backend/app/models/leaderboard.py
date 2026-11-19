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
    net_pnl: float = Field(  # gross_pnl - fees: the ranking measure
        validation_alias="netPnl", serialization_alias="netPnl"
    )
    gross_pnl: float = Field(  # sum of closedPnl (before fees)
        validation_alias="grossPnl", serialization_alias="grossPnl"
    )
    # Where gross_pnl came from; the three always add up to it.
    trading_pnl: float = Field(  # Buy / Sell fills
        validation_alias="tradingPnl", serialization_alias="tradingPnl"
    )
    settlement_pnl: float = Field(  # Settlement fills
        validation_alias="settlementPnl", serialization_alias="settlementPnl"
    )
    conversion_pnl: float = Field(  # merges, splits, negations
        validation_alias="conversionPnl", serialization_alias="conversionPnl"
    )
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
    window_start: datetime | None = Field(
        validation_alias="windowStart", serialization_alias="windowStart"
    )
    generated_at: datetime = Field(
        validation_alias="generatedAt", serialization_alias="generatedAt"
    )
    traders_known: int = Field(  # discovered by the trade stream
        validation_alias="tradersKnown", serialization_alias="tradersKnown"
    )
    traders_pending: int = Field(  # discovered, never fetched
        validation_alias="tradersPending", serialization_alias="tradersPending"
    )
    traders_ranked: int = Field(  # complete, with fills in window
        validation_alias="tradersRanked", serialization_alias="tradersRanked"
    )
    # Left out because their stored fills do not cover this window yet
    # (pending traders included).
    traders_excluded: int = Field(
        validation_alias="tradersExcluded", serialization_alias="tradersExcluded"
    )
    rows: list[LeaderboardRow]  # best first; the first 'limit' only