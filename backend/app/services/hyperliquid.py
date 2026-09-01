"""Client for HL public info API

This module is the only place in the backend that knows how to communicate 
with Hyperliquid. It returns raw API responses, normalization layer will 
be responsible for converting raw API responses to the app's domain model
"""

from typing import Any

import httpx

HYPERLIQUID_API_BASE_URL = "https://api.hyperliquid.xyz"

# Fail fast if HL is slow or unreachable
# up to 5s to establish connection, 10s total for the request
REQUEST_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

class HyperliquidError(Exception):
    """Raised when a Hyperliquid request fails for any reason
    
    Callers should catch this instead of httpx exceptions, so the 
    rest of the app never depends on the HTTP library choice
    """

class HyperliquidClient:
    """Makes info requests agains the HL public API
    
    Takes an httpx.AsyncClient so one connection pool can be shared
    across all requests for the lifetime of the application
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def fetch_outcome_meta(self) -> dict[str, Any]:
        """Fetch all live outcome markets, questions, and deployers.
        
        Raw response shape:
        {"outcomes": [...], "questions": [...], "deployers": [...], "feeScale": ...}
        """
        data = await self._post_info({"type": "outcomeMeta"})
        if not isinstance(data, dict) or "outcomes" not in data:
            raise HyperliquidError(
                f"Unexpected outcomeMeta response shape: {type(data).__name__}"
            )
        return data
    
    async def fetch_all_mids(self) -> dict[str, str]:
        """Fetch mid prices for all coins
        
        Outcome coins appear as keys ("#12100") w/ price as a string:
        {"#12100": "0.05306", ...}.
        """
        data = await self._post_info({"type": "allMids"})
        if not isinstance(data, dict):
            raise HyperliquidError(
                f"Unexpected allMids response shape: {type(data).__name__}"
            )
        return data