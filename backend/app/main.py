from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field


app = FastAPI(title="Hyperliquid Outcomes API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str


class MarketOutcome(BaseModel):
    side: Literal["YES", "NO"]
    price: float


class OutcomeMarket(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    question: str
    status: Literal["open", "closed"]
    closes_at: str = Field(alias="closesAt")
    outcomes: list[MarketOutcome]


FAKE_MARKETS = [
    OutcomeMarket(
        id="btc-100k",
        question="Will Bitcoin be above $100,000 at the end of the year?",
        status="open",
        closes_at="2026-12-31T23:59:59Z",
        outcomes=[
            MarketOutcome(side="YES", price=0.64),
            MarketOutcome(side="NO", price=0.36),
        ],
    ),
    OutcomeMarket(
        id="eth-5k",
        question="Will Ethereum trade above $5,000 before the end of the year?",
        status="open",
        closes_at="2026-12-31T23:59:59Z",
        outcomes=[
            MarketOutcome(side="YES", price=0.41),
            MarketOutcome(side="NO", price=0.59),
        ],
    ),
    OutcomeMarket(
        id="sol-300",
        question="Will Solana trade above $300 before the end of the year?",
        status="open",
        closes_at="2026-12-31T23:59:59Z",
        outcomes=[
            MarketOutcome(side="YES", price=0.27),
            MarketOutcome(side="NO", price=0.73),
        ],
    ),
]


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/markets")
async def markets() -> list[OutcomeMarket]:
    return FAKE_MARKETS