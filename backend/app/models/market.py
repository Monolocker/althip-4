"""Application's internal domain models as Pydantic classes for outcome markets

Essentially, the backend twin of frontend/src/types/market.ts. These models are 
what the rest of the backend (and frontend, via JSON) depend on. Purposely, the 
models do not mirror HL's raw response shapes. The normalization layer converts
between the two (pydantic domain models and raw HL response shapes).
"""

from datetime import datetime 
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

class OutcomeSide(BaseModel):
    """One tradable side of an outcome market (Yes or No)"""

    index: int  # O or 1, the "side" in the encoding formula
    label: str  # display label, ex: "Yes" (cleaned of template: prefixes)
    coin: str   # HL coin string, ex: "#12100", needed for books later
    price: float | None = None  # market-implied probability, None if unknown, not 0 

class OutcomeMarket(BaseModel):
    """A single outcome market, normalized for our application"""

    model_config = ConfigDict(populate_by_name=True) # May have to change to validate_by_name to comply w/ new pydantic

    id: str     # HL outcome id as a string
    name: str   # raw HL name, ex: "template:priceTouch"
    question: str   # human-readable display summary. This is not resolution criteria 
    description: str # raw HL spec string, keyword:value|keyword:value. Ex: class:priceBinary|underlying:BTC and so on
    status: Literal["open", "settled"] = "open"
    closes_at: datetime | None = Field(default=None, alias="closesAt")
    quote_token: str = Field(default="USDC", alias="quoteToken")
    venue: str = ""
    sides: list[OutcomeSide]
