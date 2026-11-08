"""What it would cost to trade, venue by venue (Milestone 22.4)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.venue import MatchLevel

ExecutionVenue = Literal["hyperliquid", "polymarket", "kalshi"]


class VenueCost(BaseModel):
    """Buying `size` contracts of this outcome's Yes side on one venue,
    by crossing the book now (taker), at the venue's base fee rate."""

    model_config = ConfigDict(populate_by_name=True)

    venue: ExecutionVenue
    external_id: str | None = Field(alias="externalId")  # None for Hyperliquid
    title: str
    # None for Hyperliquid itself; otherwise the confirmed link's level.
    match_level: MatchLevel | None = Field(alias="matchLevel")
    filled: float = 0.0  # contracts the book can supply now
    unfilled: float = 0.0  # contracts the book cannot supply at any price
    best_ask: float | None = Field(default=None, alias="bestAsk")
    mid: float | None = None
    average_price: float | None = Field(default=None, alias="averagePrice")
    # average_price - best_ask: what walking down the book adds per contract
    slippage: float | None = None
    fee_now: float = Field(default=0.0, alias="feeNow")  # $ paid when buying
    # $ deducted at settlement if the outcome wins (Hyperliquid only).
    fee_if_wins: float = Field(default=0.0, alias="feeIfWins")
    # (average_price * filled + fee_now) / filled: dollars per contract.
    cost_per_contract: float | None = Field(default=None, alias="costPerContract")
    # cost_per_contract / (1 - fee_if_wins per contract): the probability
    # at which buying here exactly breaks even. Comparable across venues
    # whether a fee is charged now or at settlement.
    break_even: float | None = Field(default=None, alias="breakEven")
    fee_basis: str = Field(default="", alias="feeBasis")
    warnings: list[str] = Field(default_factory=list)
    book_time: datetime | None = Field(default=None, alias="bookTime")
    error: str | None = None


class ExecutionEstimate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    market_id: str = Field(alias="marketId")
    size: float
    settles_at: datetime | None = Field(alias="settlesAt")  # holding period end
    assumptions: list[str]
    venues: list[VenueCost]