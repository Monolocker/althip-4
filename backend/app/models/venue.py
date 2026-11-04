"""A market on another venue, in domain app shape (M22)

Polymarket and Kalshi describe markets very differently;
each adapter (services/polymarket.py, services/kalshi.py)
translates its venue's raw response into VenueQuote, so
the rest of the app compares like with like and never learns
either venue's field names
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Venue = Literal["polymarket", "kalshi"]

# 22.2, decision 2: "identical" = same payout in every scenario
# "comparable" = same in the normal case, different at edges (and
# then a note stating how is required)
MatchLevel = Literal["identical", "comparable"]

class VenueQuote(BaseModel):
    """One binary market elsewhere, priced on its "Yes side."""

    model_config = ConfigDict(populate_by_name=True)

    venue: Venue
    external_id: str = Field(alias="externalId")    # Polymarket id / Kalshi ticker
    title: str
    # The side the prices refer to: "Yes" for nearly every market
    side_label: str = Field(alias="sideLabel")
    # Best bid / best ask / a reference price for that side, in dollars
    # per $1 contract (0.43 = 43c). None when the venue reports none
    bid: float | None
    ask: float | None
    price: float | None
    status: str     # the venue's own word: "active", "closed", "open", ...
    closes_at: datetime | None = Field(alias="closesAt")
    rules: str 
    fetched_at: datetime = Field(alias="fetchedAt")

class VenueLink(BaseModel):
    """A confirmed link: one HL outcome <-> one external market"""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    market_id: str = Field(alias="marketId")
    venue: Venue
    external_id: str = Field(alias="externalId")
    match_level: MatchLevel = Field(alias="matchLevel")
    note: str
    created_at: datetime = Field(alias="createdAt")

    
class LinkTarget(BaseModel):
    """one outcome-to-market pair inside a confirmation"""

    model_config = ConfigDict(populate_by_name=True)

    market_id: str = Field(alias="marketId")
    external_id: str = Field(alias="externalId")

class LinkGroupCreate(BaseModel):
    """Request body for POST /links: a whole match confirmed at once
    (decision 1), all with the same venue, level, and note."""

    model_config = ConfigDict(populate_by_name=True)

    venue: Venue
    match_level: MatchLevel = Field(alias="matchLevel")
    note: str = ""
    links: list[LinkTarget] = Field(min_length=1)


class SuggestedPair(BaseModel):
    """One Hyperliquid outcome and the external market it seems to match."""

    model_config = ConfigDict(populate_by_name=True)

    market_id: str = Field(alias="marketId")
    outcome_label: str = Field(alias="outcomeLabel")
    quote: VenueQuote


class Suggestion(BaseModel):
    """A candidate match on one venue, for a person to confirm (22.2)."""

    model_config = ConfigDict(populate_by_name=True)

    venue: Venue
    event_title: str = Field(alias="eventTitle")
    pairs: list[SuggestedPair]
    # Hyperliquid outcomes with no counterpart found (always the fallback).
    unmatched: list[str]
    # One market's full rules: what the person compares before confirming.
    rules: str


class ElsewhereEntry(BaseModel):
    """A confirmed link plus its live quote, or why there is none."""

    model_config = ConfigDict(populate_by_name=True)

    link: VenueLink
    quote: VenueQuote | None
    error: str | None
