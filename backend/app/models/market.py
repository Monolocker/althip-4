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

class BookSummary(BaseModel):
    """How much a market's displayed price can be trusted (Milestone 18.3b).

    Built from the background book sweep, which is minutes old by design:
    it answers "is there a real market here?" for display only and must
    never feed an order decision.
    """

    model_config = ConfigDict(populate_by_name=True)

    # tight: spread <= 2c. wide: <= 10c. unreliable: > 10c, empty, one-sided,
    # or a never-traded market (placeholder mark of 0.5).
    quality: Literal["tight", "wide", "unreliable"]
    # "sweep": measured from the order book. "mark": inferred from the
    # placeholder mark because no fresh sweep data exists yet.
    source: Literal["sweep", "mark"]
    bid: float | None = None
    ask: float | None = None
    spread: float | None = None
    checked_at: datetime | None = Field(default=None, alias="checkedAt")

class QuestionRef(BaseModel):
    """Compact link from an outcome to its multi-outcome question (18.6a).

    Carried on every list item so the frontend can group a question's
    outcomes into one card without a second request.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str  # Hyperliquid question id, e.g. "419"
    # Rendered question title, e.g. "UEFA Europa League Matchday 3:
    # Juventus v Stade Rennais FC". None without a template.
    title: str | None = None
    role: Literal["named", "fallback"]
    # This outcome's own name within the question: "Juventus", "Draw",
    # "Fallback". The full title of the market stays in `question`.
    outcome_label: str = Field(alias="outcomeLabel")


class SpecDifference(BaseModel):
    """One spec field where two same-titled markets disagree (20.3)."""

    model_config = ConfigDict(populate_by_name=True)

    key: str  # spec key, e.g. "listingDeadline"
    this_value: str = Field(alias="thisValue")  # display-formatted
    other_value: str = Field(alias="otherValue")  # display-formatted


class Lookalike(BaseModel):
    """Another live market with the SAME title but DIFFERENT rules (20.3).

    Same template + same spec = identical rules; same title alone does
    not imply that, because a template's title need not mention every
    spec field (e.g. an IPO market's title omits its listing deadline).
    """

    model_config = ConfigDict(populate_by_name=True)

    market_id: str = Field(alias="marketId")
    venue: str
    differences: list[SpecDifference]


class OutcomeMarket(BaseModel):
    """A single outcome market, normalized for our application."""

    model_config = ConfigDict(populate_by_name=True)

    id: str  # Hyperliquid outcome id as a string, e.g. "1210"
    name: str  # raw Hyperliquid name, e.g. "template:priceTouch"
    question: str  # human-readable display summary (NOT resolution criteria)
    description: str  # raw Hyperliquid spec string; the source of truth
    status: Literal["open", "settled"] = "open"
    # When the deciding event is scheduled: price observation time, game
    # start, scheduled decision. None when the spec names no event time.
    event_at: datetime | None = Field(default=None, alias="eventAt")
    # Latest expected resolution time. Equal to event_at for price markets;
    # a separate, later deadline for sports, policy, awards and IPOs.
    resolves_by: datetime | None = Field(default=None, alias="resolvesBy")
    quote_token: str = Field(default="USDC", alias="quoteToken")
    venue: str = ""
    sides: list[OutcomeSide]
    # Contracts traded in the last 24h (HL dayBaseVlm). Total USDC 
    # traded across both sides of the outcome market. None when HL
    # reported no trading context
    volume_24h: float | None = Field(default=None, alias="volume24h")
    # Side-0 price about 24h ago (HL prevDayPx; observed in 20.2 to match
    # the candle from 24h earlier within ~0.3c). None when HL reports 0.0,
    # which means "no history" (never traded, or younger than a day).
    price_24h_ago: float | None = Field(default=None, alias="price24hAgo")
    # Current side-0 price minus price_24h_ago, in price units (0.054 =
    # +5.4 percentage points). None whenever either price is missing.
    change_24h: float | None = Field(default=None, alias="change24h")
    # Side-0 book quality; None when there is no evidence either way
    book: BookSummary | None = None
    # "binary" = each sides settles to $1 or $0. Thus, a side's price
    # is a market-implied probablility. "scalar" = sides pay out 
    # proportionally (long/short on a price range). Prices != prob
    payout: Literal["binary", "scalar"] = "binary"
    # Set when this market belongs to a multi-outcome question
    parent: QuestionRef | None = None
    # HL's own category for the market's template
    # e.g. "sports", "price", "culture". None when no template
    category: str | None = None
    # Same-titled markets whose rules differ. Filled in by the snapshot
    # after normalization; empty when there are none.
    lookalikes: list[Lookalike] = Field(default_factory=list)


class QuestionMembership(BaseModel):
    """How an outcome relates to a multi-outcome question, if at all."""

    model_config = ConfigDict(populate_by_name=True)

    question_id: str = Field(alias="questionId")
    name: str
    description: str
    is_fallback: bool = Field(alias="isFallback")
    # Other outcomes belonging to the same question, excluding this one.
    sibling_ids: list[str] = Field(alias="siblingIds")
    # Rendered from the question's template (M18.1b); None when the 
    # template is unknown or a placeholder has no value
    title: str | None = None
    rules: str | None = None


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
    # This market's resolution rules, rendered from its template's
    # description (M18.1b). None w/o a template
    rules: str | None = None