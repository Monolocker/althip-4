"""Domain models for per-deployer statistics (Milestone 20)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QualityCounts(BaseModel):
    """How many of a deployer's markets fall in each book-quality class."""

    tight: int = 0
    wide: int = 0
    unreliable: int = 0
    unknown: int = 0  # no book data yet (sweep pending)


class DeployerStats(BaseModel):
    """One deployer (venue) summarized from the current snapshot."""

    model_config = ConfigDict(populate_by_name=True)

    venue: str  # "" for Hyperliquid's own markets
    address: str | None  # None for Hyperliquid's own markets
    # Distinct operator addresses the deployer authorized (subDeployers).
    operator_count: int = Field(alias="operatorCount")
    market_count: int = Field(alias="marketCount")  # live outcomes
    question_count: int = Field(alias="questionCount")
    volume_24h: float = Field(alias="volume24h")  # summed side-0 dayBaseVlm
    book_quality: QualityCounts = Field(alias="bookQuality")
    categories: dict[str, int]  # template category -> outcome count
    next_event_at: datetime | None = Field(alias="nextEventAt")
    top_market_id: str | None = Field(alias="topMarketId")
    top_market_question: str | None = Field(alias="topMarketQuestion")