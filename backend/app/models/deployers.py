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
    operator_count: int = Field(
        validation_alias="operatorCount", serialization_alias="operatorCount"
    )
    market_count: int = Field(  # live outcomes
        validation_alias="marketCount", serialization_alias="marketCount"
    )
    question_count: int = Field(
        validation_alias="questionCount", serialization_alias="questionCount"
    )
    volume_24h: float = Field(  # summed side-0 dayBaseVlm
        validation_alias="volume24h", serialization_alias="volume24h"
    )
    book_quality: QualityCounts = Field(
        validation_alias="bookQuality", serialization_alias="bookQuality"
    )
    categories: dict[str, int]  # template category -> outcome count
    next_event_at: datetime | None = Field(
        validation_alias="nextEventAt", serialization_alias="nextEventAt"
    )
    top_market_id: str | None = Field(
        validation_alias="topMarketId", serialization_alias="topMarketId"
    )
    top_market_question: str | None = Field(
        validation_alias="topMarketQuestion", serialization_alias="topMarketQuestion"
    )