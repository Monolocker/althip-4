"""Domain models for price history (Milestone 19.1)"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The chart ranges the frontend can ask for. A Literal type makes FastAPI
# reject anything else w/ a 422 (unprocessable content) before our code runs
CandleRange = Literal["1d", "1w", "1m", "all"]

class Candle(BaseModel):
    """One interval of a market's side-0 price history"""

    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float   # Contracts traded in the interval
    # Number of trades. Can be 0: HL also records candles for 
    # some intervals w/o trades, their prices are not trade prices
    trades: int


class PriceHistory(BaseModel):
    """A market's candles for one chart range"""

    model_config = ConfigDict(populate_by_name=True)

    market_id: str = Field(alias="marketId")
    coin: str   # always side 0: side 1's history mirrors it exactly
    range: CandleRange
    interval: str   # HL candle interval used, e.g. "1h"
    candles: list[Candle]   # oldest first; empty if never traded
    fetched_at: datetime = Field(alias="fetchedAt")