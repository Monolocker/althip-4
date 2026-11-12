"""Domain models for the unified feed (Milestone 24)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Interleaving order of the feed, one item of each kind in turn.
FeedKind = Literal["news", "sports", "ticker", "trending"]


class FeedItem(BaseModel):
    """One feed entry, whatever its source. The UI never sees a raw
    Google, ESPN or Hyperliquid shape: each source is normalized to this."""

    model_config = ConfigDict(populate_by_name=True)

    kind: FeedKind
    text: str  # full text, never truncated: shortening is the UI's job
    url: str | None = None  # external link: an article or a trade page
    market_id: str | None = Field(default=None, alias="marketId")  # trending: one of ours
    source: str | None = None  # outlet or venue, e.g. "ESPN", "Reuters"
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    # ticker: 24h price change as a fraction (0.0201 = +2.01%); None
    # when Hyperliquid has no price from a day ago.
    change_24h: float | None = Field(default=None, alias="change24h")
    # trending: side-0 implied probability (binary markets only).
    probability: float | None = None


class FeedSourceStatus(BaseModel):
    """Whether one source's latest refresh worked, and how old its items are."""

    model_config = ConfigDict(populate_by_name=True)

    kind: FeedKind
    ok: bool  # the latest refresh succeeded
    items: int
    # When the items shown were fetched. A failed refresh keeps the last
    # good items, so this can be older than the failure.
    fetched_at: datetime | None = Field(alias="fetchedAt")
    error: str | None = None


class Feed(BaseModel):
    """Every source's items, interleaved, plus each source's health."""

    model_config = ConfigDict(populate_by_name=True)

    generated_at: datetime = Field(alias="generatedAt")
    items: list[FeedItem]
    sources: list[FeedSourceStatus]