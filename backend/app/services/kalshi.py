"""Read-only adapter for Kalshi market data (Milestone 22.1).

Uses Kalshi's public Trade API v2 market endpoints (no key needed for
market data) and translates one market into our VenueQuote. The only
module that knows Kalshi's URLs and field names.

Observed in the 22 probes (Nov 2026):
  - Prices are dollar STRINGS: "yes_bid_dollars": "0.1100".
  - Hierarchy is series -> events -> markets; a market's identifier is
    its ticker. Rules are "rules_primary" plus "rules_secondary".
  - There is no keyword search; markets are found through series.
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from app.models.venue import VenueQuote

KALSHI_URL = "https://api.elections.kalshi.com/trade-api/v2"
REQUEST_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class KalshiError(Exception):
    """Raised when a Kalshi request fails for any reason."""


class KalshiClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def fetch_market(self, ticker: str) -> dict[str, Any] | None:
        """One market by ticker, or None if Kalshi has no such market.

        Raw shape: {"market": {...}}; this returns the inner object.
        """
        try:
            response = await self._http.get(
                f"{KALSHI_URL}/markets/{ticker}", timeout=REQUEST_TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise KalshiError(f"Kalshi request failed: {exc}") from exc
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise KalshiError(f"Kalshi returned HTTP {response.status_code}")
        data = response.json()
        market = data.get("market") if isinstance(data, dict) else None
        if not isinstance(market, dict):
            raise KalshiError("Unexpected market shape: no 'market' object")
        return market
    

    async def fetch_series(self) -> list[dict[str, Any]]:
        """Every series (about 15,000): ticker, title, category, fees, ...

        A large response, so callers should cache it (suggestions keep
        it for a day).
        """
        data = await self._get_json(f"{KALSHI_URL}/series", timeout=60.0)
        series = data.get("series") if isinstance(data, dict) else None
        if not isinstance(series, list):
            raise KalshiError("Unexpected series shape: no 'series' list")
        return series

    async def fetch_open_events(self, series_ticker: str) -> list[dict[str, Any]]:
        """Open events of one series, each with its markets nested inside."""
        data = await self._get_json(
            f"{KALSHI_URL}/events",
            params={
                "series_ticker": series_ticker,
                "status": "open",
                "with_nested_markets": "true",
                "limit": 200,
            },
        )
        events = data.get("events") if isinstance(data, dict) else None
        if not isinstance(events, list):
            raise KalshiError("Unexpected events shape: no 'events' list")
        return events

    async def _get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        try:
            response = await self._http.get(
                url,
                params=params,
                timeout=httpx.Timeout(timeout, connect=5.0) if timeout else REQUEST_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise KalshiError(f"Kalshi request failed: {exc}") from exc
        if response.status_code != 200:
            raise KalshiError(f"Kalshi returned HTTP {response.status_code}")
        return response.json()


def _side(price: Any, size: Any) -> float | None:
    """A best price, or None when nothing rests there (22.2).

    Evidence from the first 22 probe: an empty side was reported as
    price "0.0000" WITH size "0.00". A price with zero size is no order,
    so it becomes None, never a 0c bid. A missing size field is not
    treated as empty: then the price is kept as given.
    """
    if _dollars(size) == 0:
        return None
    return _dollars(price)


def _dollars(value: Any) -> float | None:
    """'0.1100' -> 0.11. Kalshi reports an empty side as 0, kept as given."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def kalshi_quote(raw: dict[str, Any]) -> VenueQuote:
    """Translate one Kalshi market into a VenueQuote for its Yes side."""
    title = str(raw.get("title", ""))
    subtitle = raw.get("yes_sub_title")
    rules = "\n\n".join(
        str(part) for part in (raw.get("rules_primary"), raw.get("rules_secondary")) if part
    )
    return VenueQuote(
        venue="kalshi",
        external_id=str(raw.get("ticker", "")),
        title=f"{title} ({subtitle})" if subtitle and subtitle not in title else title,
        side_label="Yes",
        bid=_side(raw.get("yes_bid_dollars"), raw.get("yes_bid_size_fp")),
        ask=_side(raw.get("yes_ask_dollars"), raw.get("yes_ask_size_fp")),
        price=_dollars(raw.get("last_price_dollars")),
        status=str(raw.get("status", "")),
        closes_at=_time(raw.get("close_time")),
        rules=rules,
        fetched_at=datetime.now(timezone.utc),
    )