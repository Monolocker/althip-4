"""A market on another venue, in domain app shape (M22)

Polymarket and Kalshi describe markets very differently;
each adapter (services/polymarket.py, services/kalshi.py)
translates its venue's raw reposne into this one model, so
the rest of the app compares like with like and never learns
either venue's field names
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Venue = Literal["polymarket", "kalshi"]


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
    closes_at: datetime | None = Field(alias="closestAt")
    rules: str 
    fetched_at: datetime = Field(alias="fetchedAt")