"""Domain model for an order book snapshot."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class BookLevel(BaseModel):
    """One price level: aggregated resting orders at a single price"""

    price: float    # probability, like 0.21
    size: float     # total contracts resting at this price
    orders: int     # number of distinct orders making up that size

class OrderBook(BaseModel):
    """A snapshot of one side's order book at a moment in time
    
    Both lists are ordered best-first: bids descending by price,
    asks ascending by price
    """

    model_config = ConfigDict(populate_by_name=True)

    coin: str   # e.g. "#12100"
    side_index: int = Field(  # 0 or 1
        validation_alias="sideIndex", serialization_alias="sideIndex"
    )
    fetched_at: datetime = Field(  # Hyperliquid's timestamp
        validation_alias="fetchedAt", serialization_alias="fetchedAt"
    )
    bids: list[BookLevel]
    asks: list[BookLevel]
    best_bid: float | None = Field(
        default=None, validation_alias="bestBid", serialization_alias="bestBid"
    )
    best_ask: float | None = Field(
        default=None, validation_alias="bestAsk", serialization_alias="bestAsk"
    )
    spread: float | None = None # best_ask - best_bid, when both exist