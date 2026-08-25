from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(title="Hyperliquid Outcomes API")


class HealthResponse(BaseModel):
    status: str


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")