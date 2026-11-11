"""Domain models for trader leaderboard (Milestone 23.3)"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

# Rolling windows ending now; "all" = since app began tracking
LeaderboardWindow = Literal["24h", "7d", "30d", "all"]
LeaderboardSort = Literal["pnl", "volume", "fills"]
# "full": every fill inside the window is stored. "Partial" = 
# this trader's stored history starts after the window does
Coverage = Literal["full", "partial"]

class LeaderboardRow(BaseModel):
    """One trader's realized results inside one window. Money in USDC."""

    model_config = ConfigDict(populate_by_name=True)

    address: str
    net_pnl: float = Field(alias="netPnl")  # gross_pnl - fees
    gross_pnl: float = Field(alias="grossPnl")  # sum of closedPnl (before fees)
    # Where gross_pnl came from; the three always add up to it.
    trading_pnl: float = Field(alias="tradingPnl")  # Buy / Sell fills
    settlement_pnl: float = Field(alias="settlementPnl")  # Settlement fills
    conversion_pnl: float = Field(alias="conversionPnl")  # merges, splits, negations
    fees: float
    volume: float  # USDC notional of Buy / Sell fills only
    fills: int
    markets: int  # distinct outcomes (both sides of a market count once)
    settlements_won: int = Field(alias="settlementsWon")  # settled at 1
    settlements_lost: int = Field(alias="settlementsLost")  # settled at 0
    settlements_fractional: int = Field(alias="settlementsFractional")  # between
    coverage: Coverage
    coverage_from: datetime | None = Field(alias="coverageFrom")
    fills_through: datetime = Field(alias="fillsThrough")
    # The trade stream has seen a trade of theirs that is not fetched yet.
    behind: bool

class Leaderboard(BaseModel):
    """Traders ranked within one window, with honest coverage context"""

    model_config = ConfigDict(populate_by_name=True)

    window: LeaderboardWindow
    sort: LeaderboardSort
    window_start: datetime | None = Field(alias="windowStart")  # None: nothing tracked yet
    # Earliest moment any stored trader's fills are complete from
    tracking_since: datetime | None = Field(alias="trackingSince")
    generated_at: datetime = Field(alias="generatedAt")
    traders_known: int = Field(alias="tradersKnown")  # siscovered by the trade stream
    traders_pending: int = Field(alias="tradersPending")  # discovered, never fetched
    traders_ranked: int = Field(alias="tradersRanked")    # fetched, w/ fills in window
    rows: list[LeaderboardRow]  # best first; the first 'limit' only