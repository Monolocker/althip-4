"""Domain models for one trader's HIP-4 dashboard (Milestone 26.2).

Window figures (stats, chart, resolved markets) come from stored fills
and follow the leaderboard's definitions (26.1): realized PnL after
fees, Buy + Sell volume, wins and losses per market. Positions and
orders are LIVE: read from Hyperliquid when the dashboard is requested.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.leaderboard import LeaderboardWindow


class TraderStats(BaseModel):
    """Realized results inside the window. Money in USDC."""

    model_config = ConfigDict(populate_by_name=True)

    net_pnl: float = Field(  # gross_pnl - fees
        validation_alias="netPnl", serialization_alias="netPnl"
    )
    gross_pnl: float = Field(  # sum of closedPnl (before fees)
        validation_alias="grossPnl", serialization_alias="grossPnl"
    )
    fees: float
    volume: float  # USDC notional of Buy / Sell fills only
    markets: int  # distinct outcomes traded in the window
    wins: int  # markets with something realized and net PnL above 0
    losses: int  # ... and net PnL below 0
    accuracy: float | None  # wins / (wins + losses); None when both are 0


class BiggestWin(BaseModel):
    """The best single market of the window, by net PnL (decision, 26.0)."""

    model_config = ConfigDict(populate_by_name=True)

    market_id: str = Field(  # outcome id: opens in our app
        validation_alias="marketId", serialization_alias="marketId"
    )
    title: str | None  # None if this app never recorded the market
    net_pnl: float = Field(validation_alias="netPnl", serialization_alias="netPnl")


class PnlPoint(BaseModel):
    """Cumulative net realized PnL at the end of one time bucket."""

    time: datetime
    pnl: float


class ResolvedMarket(BaseModel):
    """One market with something realized in the window: a win or a loss."""

    model_config = ConfigDict(populate_by_name=True)

    market_id: str = Field(validation_alias="marketId", serialization_alias="marketId")
    title: str | None
    net_pnl: float = Field(validation_alias="netPnl", serialization_alias="netPnl")
    fees: float
    volume: float
    result: Literal["win", "loss", "even"]
    # True if the market settled for this trader (a Settlement fill);
    # False if they closed out by selling or converting.
    settled: bool
    last_fill_at: datetime = Field(validation_alias="lastFillAt", serialization_alias="lastFillAt")


class TraderPosition(BaseModel):
    """One live outcome balance (spotClearinghouseState, 26.0b)."""

    model_config = ConfigDict(populate_by_name=True)

    coin: str  # "#N": the side's trading coin
    market_id: str = Field(validation_alias="marketId", serialization_alias="marketId")
    title: str
    side_label: str = Field(validation_alias="sideLabel", serialization_alias="sideLabel")
    shares: float  # balance "total"
    on_hold: float = Field(  # "hold": locked by open orders
        validation_alias="onHold", serialization_alias="onHold"
    )
    entry_notional: float | None = Field(  # "entryNtl": cost basis
        validation_alias="entryNotional", serialization_alias="entryNotional"
    )
    price: float | None  # market-implied probability now; None if unknown
    value: float | None  # shares * price; None when the price is unknown


class TraderPositions(BaseModel):
    """Live positions in markets that are still open."""

    model_config = ConfigDict(populate_by_name=True)

    value: float  # sum of the priced positions' values
    unpriced: int  # positions with no usable price, left out of `value`
    count: int  # open positions (non-zero balances in live markets)
    biggest: TraderPosition | None  # largest single side by value
    items: list[TraderPosition]  # biggest value first, unpriced last


class TraderOrder(BaseModel):
    """One resting outcome order (frontendOpenOrders, 26.0)."""

    model_config = ConfigDict(populate_by_name=True)

    coin: str
    market_id: str = Field(validation_alias="marketId", serialization_alias="marketId")
    title: str | None  # None if the market is no longer in the live snapshot
    side_label: str | None = Field(validation_alias="sideLabel", serialization_alias="sideLabel")
    direction: Literal["buy", "sell"]  # Hyperliquid side "B" / "A"
    price: float  # limit price
    size: float  # remaining
    original_size: float = Field(
        validation_alias="originalSize", serialization_alias="originalSize"
    )
    placed_at: datetime = Field(validation_alias="placedAt", serialization_alias="placedAt")
    order_type: str | None = Field(validation_alias="orderType", serialization_alias="orderType")
    tif: str | None  # time in force, e.g. "Alo" (post only), "Gtc"
    reduce_only: bool = Field(validation_alias="reduceOnly", serialization_alias="reduceOnly")


class TraderDashboard(BaseModel):
    """Everything the trader dashboard shows, for one window."""

    model_config = ConfigDict(populate_by_name=True)

    address: str
    window: LeaderboardWindow
    window_start: datetime | None = Field(  # None for All-Time
        validation_alias="windowStart", serialization_alias="windowStart"
    )
    generated_at: datetime = Field(
        validation_alias="generatedAt", serialization_alias="generatedAt"
    )
    # Same rule as the leaderboard: are this trader's stored fills
    # complete for the window? If not, figures start at history_from.
    complete: bool
    history_from: datetime | None = Field(
        validation_alias="historyFrom", serialization_alias="historyFrom"
    )
    fills_through: datetime | None = Field(
        validation_alias="fillsThrough", serialization_alias="fillsThrough"
    )
    stats: TraderStats
    biggest_win: BiggestWin | None = Field(  # None: no winning market
        validation_alias="biggestWin", serialization_alias="biggestWin"
    )
    pnl_series: list[PnlPoint] = Field(  # starts at 0 at history_from
        validation_alias="pnlSeries", serialization_alias="pnlSeries"
    )
    resolved: list[ResolvedMarket]  # most recent first
    # Live parts: None when Hyperliquid could not be reached; live_error
    # then says why, and the stored figures above are still valid.
    positions: TraderPositions | None
    orders: list[TraderOrder] | None  # newest first
    live_error: str | None = Field(validation_alias="liveError", serialization_alias="liveError")