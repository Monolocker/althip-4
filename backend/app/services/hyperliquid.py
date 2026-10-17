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
    
    async def fetch_spot_asset_ctxs(self) -> list[dict[str, Any]]:
        """Fetch 24h trading context (volume, prices) for every spot coin.

        Documented for spot pairs. Observed in M17.5, but NOT documented:
        outcome coins ("#128770") appear here too, e.g.
        {"coin": "#128770", "dayBaseVlm": "21876.0", "dayNtlVlm": "10220.04",
        "markPx": "0.2444", "midPx": "0.2559", "prevDayPx": "0.5236", ...}

        Raw response shape: [spotMeta, [ctx, ctx, ...]]. Returns the ctx list
        """

        data = await self._post_info({"type": "spotMetaAndAssetCtxs"})
        if not (
            isinstance(data, list) and len(data) == 2 and isinstance (data[1], list)
        ):
            raise HyperliquidError(
                "Unexpected spotMetaAndAssetCtxs response shape: "
                f"{type(data).__name__}"
            )
        return data[1]
    
    async def fetch_outcome_templates(self) -> list[dict[str, Any]]:
        """Fetch validator-approved templates every HIP-4 market comes from.
        
        Verified live shape example:
        {"id": "binaryPrice",
         "name": "{perp} above {threshold} at {time}?",
         "description": "The market resolves to Yes if ...",
         "keywords": [...],
         "role": {"standaloneOutcome": {"sideNames": ["Yes", "No"]}}}
        role is also {"questionOutcome": {"parent": "<question template id>"}}
        or the string "question".
        """
        data = await self._post_info({"type": "outcomeTemplates"})
        if not isinstance(data, list):
            raise HyperliquidError(
                f"Unexpected outcomeTemplates reponse shape: {type(data).__name__}"
            )
        return data
    
    async def fetch_settled_outcome(
        self, outcome_id: int
    ) -> dict[str, Any] | None: 
        """Fetch settlement info for an outcome that is no longer live.

        Verified live shape:
        {"spec": {<the original outcome object>},
         "settleFraction": "1.0", "details": "template"}

        Returns None when the response carries no settlement record.
        """
        data = await self._post_info(
            {"type": "settledOutcome", "outcome": outcome_id}
        )
        if not isinstance(data, dict) or "spec" not in data:
            return None
        return data
    
    async def fetch_l2_book(self, coin: str) -> dict[str, Any]:
        """Fetch an order book snapshot for one coin, such as "#12100"

        Verified live shape:
        {"coin": "#12100", "time": 1788224478920,
         "levels": [[{"px": "0.05", "sz": "11487.0", "n": 6}, ...],     # bids
                    [{"px": "0.06", "sz": "500.0", "n": 1}, ...]]}      # asks
        n = number of levels. Up to 20 levels per side
        """
        data = await self._post_info({"type": "l2Book", "coin": coin})
        if not isinstance(data, dict) or "levels" not in data:
            raise HyperliquidError(
                f"Unexepected l2Book response shape for {coin!r}: "
                f"{type(data).__name__}"
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
                f"{body.get('type')!r}: {type(exc).__name__}: {exc}"
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