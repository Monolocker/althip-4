"""Application's internal domain models as Pydantic classes for outcome markets

Essentially, the backend version of frontend/src/types/market.ts. These models are 
what the rest of the backend (and frontend, via JSON) depend on. Purposely, the 
models do not mirror HL's raw response shapes. The normalization layer converts
between the two (pydantic domain models and raw HL response shapes).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OutcomeSide(BaseModel):
    """One tradable side of an outcome market (e.g. Yes or No)."""

    index: int  # 0 or 1; the `side` in the encoding formula
    label: str  # display label, e.g. "Yes" (cleaned of template: prefixes)
    coin: str  # Hyperliquid coin string, e.g. "#12100"; needed for books later
    price: float | None = None  # market-implied probability; None if unknown


class OutcomeMarket(BaseModel):
    """A single outcome market, normalized for our application."""

    model_config = ConfigDict(populate_by_name=True)

    id: str  # Hyperliquid outcome id as a string, e.g. "1210"
    name: str  # raw Hyperliquid name, e.g. "template:priceTouch"
    question: str  # human-readable display summary (NOT resolution criteria)
    description: str  # raw Hyperliquid spec string; the source of truth
    status: Literal["open", "settled"] = "open"
    closes_at: datetime | None = Field(default=None, alias="closesAt")
    quote_token: str = Field(default="USDC", alias="quoteToken")
    venue: str = ""
    sides: list[OutcomeSide]


class QuestionMembership(BaseModel):
    """How an outcome relates to a multi-outcome question, if at all."""

    model_config = ConfigDict(populate_by_name=True)

    question_id: str = Field(alias="questionId")
    name: str
    description: str
    is_fallback: bool = Field(alias="isFallback")
    # Other outcomes belonging to the same question, excluding this one.
    sibling_ids: list[str] = Field(alias="siblingIds")


class Settlement(BaseModel):
    """How a settled market resolved."""

    model_config = ConfigDict(populate_by_name=True)

    # Payout per unit to side 0 (e.g. Yes): 1.0 = side 0 won, 0.0 = side 1 won.
    settle_fraction: float | None = Field(default=None, alias="settleFraction")
    details: str = ""
    # Derived: 0 or 1 for a clean win, None for partial/unknown settlements.
    winning_side_index: int | None = Field(default=None, alias="winningSideIndex")


class OutcomeMarketDetail(OutcomeMarket):
    """An OutcomeMarket plus everything else we can derive for one market."""

    spec: dict[str, str]  # the description string, parsed into fields
    deployer: str | None = None  # deployer address for this market's venue
    question_group: QuestionMembership | None = Field(
        default=None, alias="questionGroup"
    )
    settlement: Settlement | None = None  # present only when status is settled