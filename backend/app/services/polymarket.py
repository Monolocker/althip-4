"""Read-only adapter for Polymarket market data (Milestone 22.1).

Fetches from Polymarket's public Gamma API (no key needed) and
translates one market into our VenueQuote. Like hyperliquid.py, this is
the only module that knows Polymarket's URLs and field names.

Observed in the 22 probes (Nov 2026):
  - "outcomes" and "outcomePrices" are JSON lists encoded as STRINGS
    inside the JSON ("double-encoded"): '["Yes", "No"]'.
  - "bestBid" / "bestAsk" are numbers for the first outcome's token.
  - Rules are the market's "description"; a sports match is three
    separate binary markets (home win / draw / away win).
"""

import json
from datetime import datetime, timezone
from typing import Any

import httpx

from app.models.venue import VenueQuote

GAMMA_URL = "https://gamma-api.polymarket.com"
REQUEST_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class PolymarketError(Exception):
    """Raised when a Polymarket request fails for any reason."""


class PolymarketClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def fetch_market(self, market_id: str) -> dict[str, Any] | None:
        """One market by Gamma id, or None if Polymarket has no such market."""
        try:
            response = await self._http.get(
                f"{GAMMA_URL}/markets/{market_id}", timeout=REQUEST_TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise PolymarketError(f"Polymarket request failed: {exc}") from exc
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise PolymarketError(f"Polymarket returned HTTP {response.status_code}")
        data = response.json()
        if not isinstance(data, dict):
            raise PolymarketError(f"Unexpected market shape: {type(data).__name__}")
        return data

    async def search_events(self, query: str) -> list[dict[str, Any]]:
        """Gamma public search: matching events, markets nested inside.

        Fuzzy and noisy (the 22 probe returned a 2024 Belgian election for
        an FOMC query), so results are only ever suggestions, filtered by
        the caller and confirmed by a person.
        """
        try:
            response = await self._http.get(
                f"{GAMMA_URL}/public-search",
                params={"q": query},
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise PolymarketError(f"Polymarket request failed: {exc}") from exc
        if response.status_code != 200:
            raise PolymarketError(f"Polymarket returned HTTP {response.status_code}")
        data = response.json()
        events = data.get("events") if isinstance(data, dict) else None
        return events if isinstance(events, list) else []
    

def _decode_list(value: Any) -> list[Any]:
    """'["Yes", "No"]' (a string) or ["Yes", "No"] (a list) -> a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            return []
        return decoded if isinstance(decoded, list) else []
    return []


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def polymarket_quote(raw: dict[str, Any]) -> VenueQuote:
    """Translate one Gamma market into a VenueQuote for its first outcome.

    bestBid/bestAsk refer to the first outcome's token, so the quote is
    for outcomes[0] ("Yes" in a yes/no market) and says so in side_label.
    """
    outcomes = _decode_list(raw.get("outcomes"))
    prices = _decode_list(raw.get("outcomePrices"))
    if raw.get("closed"):
        status = "closed"
    elif raw.get("active"):
        status = "active"
    else:
        status = "inactive"
    return VenueQuote(
        venue="polymarket",
        external_id=str(raw.get("id", "")),
        title=str(raw.get("question", "")),
        side_label=str(outcomes[0]) if outcomes else "Yes",
        bid=_number(raw.get("bestBid")),
        ask=_number(raw.get("bestAsk")),
        price=_number(prices[0]) if prices else None,
        status=status,
        closes_at=_time(raw.get("endDate")),
        rules=str(raw.get("description") or ""),
        fetched_at=datetime.now(timezone.utc),
    )