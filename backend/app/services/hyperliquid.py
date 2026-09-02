"""Client for HL public info API

This module is the only place in the backend that knows how to communicate 
with Hyperliquid. It returns raw API responses, normalization layer will 
be responsible for converting raw API responses to the app's domain model
"""

from typing import Any

import httpx

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

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
    
    async def _post_info(self, body: dict[str, Any]) -> Any:
        """POST a request body to the info endpoint and return parsed JSON"""
        try:
            response = await self._http.post(
                HYPERLIQUID_INFO_URL,
                json=body,
                timeout=REQUEST_TIMEOUT,

            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            # The server answered, but w/ error status (4xx/5xx)
            raise HyperliquidError(
                f"Hyperliquid returned HTTP {exc.response.status_code} "
                f"for request {body.get("type")!r}"
            ) from exc
        except httpx.HTTPError as exc:
            # Top-level error, Network-level failure: DNS, connect timeout, read timeout, etc
            raise HyperliquidError(
                f"Network error calling Hyperliquid for request "
                f"{body.get("type")!r}: {exc}"
            ) from exc
        except ValueError as exc:
            # response.json failed: the body was not valid JSON
            raise HyperliquidError(
                f"Hyperliquid returned non-JSON body for request "
                f"{body.get("type")!r}"
            ) from exc
        
if __name__ == "__main__":
    # Run this module directly to prove the client works before wiring it into FastAPI
    import asyncio

    async def main() -> None:
        async with httpx.AsyncClient() as http:
            client = HyperliquidClient(http)

            meta = await client.fetch_outcome_meta()
            mids = await client.fetch_all_mids()

            outcomes = meta["outcomes"]
            print(f"outcomes: {len(outcomes)}")
            print(f"questions: {len(meta.get("questions", []))}")
            print(f"deployers: {len(meta.get("deployers", []))}")

            first = outcomes[0]
            yes_coin = f"#{10 * first["outcome"] + 0}"
            no_coin = f"#{10 * first["outcome"] + 1}"
            print(
                f"first outcome {first["outcome"]} ({first["name"]}): "
                f"{yes_coin} mid={mids.get(yes_coin)}, "
                f"{no_coin} mid={mids.get(no_coin)}"
            )

    asyncio.run(main())