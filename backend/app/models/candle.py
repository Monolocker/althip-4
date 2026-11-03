"""Domain models for price history (Milestones 19.1 and 21.3)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The chart ranges the frontend can ask for. A Literal type makes FastAPI
# reject anything else w/ a 422 (unprocessable content) before our code runs
CandleRange = Literal["1d", "1w", "1m", "all"]

# Where a history came from (21.3): Hyperliquid's candles for live
# markets, or this app's own 5-minute recordings once Hyperliquid has
# deleted them at settlement.
HistorySource = Literal["hyperliquid", "recorded"]


class Candle(BaseModel):
    """One interval of a market's side-0 price history"""

    time: datetime
    open: float
    high: float
    low: float
    close: float
    # Contracts traded in the interval. None = unknown: our recordings
    # store a rolling 24h volume, which cannot be split into intervals.
    volume: float | None
    # Number of trades. Can be 0: HL also records candles for some
    # intervals w/o trades, their prices are not trade prices. None =
    # unknown (recorded history).
    trades: int | None


class PriceHistory(BaseModel):
    """A market's candles for one chart range"""

    model_config = ConfigDict(populate_by_name=True)

    market_id: str = Field(alias="marketId")
    coin: str   # always side 0: side 1's history mirrors it exactly
    range: CandleRange
    interval: str   # candle interval used, e.g. "1h"
    candles: list[Candle]   # oldest first; empty if never traded
    fetched_at: datetime = Field(alias="fetchedAt")
    source: HistorySource = "hyperliquid"