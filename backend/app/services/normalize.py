"""Normalization layer: Raw HL data -> app domain model"""

import logging 
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

def parse_spec(description: str) -> dict[str, str]:
    """"perp:BTC|threshold:100000|time:20261001-0000"
    -> {"perp": "BTC", "threshold": "100000", "time": "20261001-0000"}

    Values may contain a colon (:), split each part on the first 
    colon only
    """
    spec: dict[str, str] = {}
    for part in description.split("|"):
        key, sep, value = part.partition(":")
        if sep:
            spec[key.strip()] = value.strip()
    return spec

def parse_hl_timestamp(value: str) -> datetime | None:
    """Parse HL's timestamp format (YYYYMMDD-HHMM) as UTC
    
    Returns None instead of raising: a bad timestamp should 
    not prevent a market from being listed
    """
    try: 
        return datetime.strptime(value, "%Y%m%d-%H%M").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None 
    
def clean_label(label: str) -> str:
    """'template:Yes' -> 'Yes'"""
    prefix = "template:"
    return label[len(prefix):] if label.startswith(prefix) else label

def _fmt_time(dt: datetime | None) -> str:
    return dt.strftime("%b %d, %Y %H:%M UTC") if dt else "expiry"

def build_question(name: str, spec: dict[str, str], closes_at: datetime | None) -> str | None:
    """Build a human-readable display summary for known dialects
    
    Returns None for unknown dialects so the caller can fall back
    to the raw description. These strings are display text only,
    exact resolution semantics live in HL's own rules
    """
    when = _fmt_time(closes_at)

    if name == "template:priceTouch" and "target" in spec:
        subject = spec.get("priceDescription") or spec.get("perp", "price")
        return f"Will {subject} touch {spec['target']} by {when}?"
    
    if name == "template:binaryPrice" and "threshold" in spec:
        subject = spec.get("priceDescription") or spec.get("perp", "price")
        return f"Will {subject} be above {spec['threshold']} at {when}?"
    
    if spec.get("class") == "priceBinary" and "targetPrice" in spec:
        subject = spec.get("underlying", "price")
        return f"Will {subject} be above {spec['targetPrice']} at {when}?"
    
def normalize_outcome(
    raw: dict[str, Any], mids: dict[str, str]
) -> OutcomeMarket:
    """Convert one raw Hyperliquid outcome + mid prices into our model."""
    outcome_id = int(raw["outcome"])
    description = raw.get("description", "")
    spec = parse_spec(description)

    # Live data uses 'time' in template markets and 'expiry' in
    # recurring ones (Milestone 7 finding).
    raw_time = spec.get("time") or spec.get("expiry")
    closes_at = parse_hl_timestamp(raw_time) if raw_time else None

    name = raw.get("name", "")
    question = build_question(name, spec, closes_at) or description or name

    sides: list[OutcomeSide] = []
    for index, side_spec in enumerate(raw.get("sideSpecs", [])[:2]):
        coin = f"#{10 * outcome_id + index}"
        raw_mid = mids.get(coin)
        try:
            price = float(raw_mid) if raw_mid is not None else None
        except ValueError:
            price = None
        sides.append(
            OutcomeSide(
                index=index,
                label=clean_label(side_spec.get("name", f"Side {index}")),
                coin=coin,
                price=price,
            )
        )

    return OutcomeMarket(
        id=str(outcome_id),
        name=name,
        question=question,
        description=description,
        status="open",
        closes_at=closes_at,
        quote_token=raw.get("quoteToken", "USDC"),
        venue=raw.get("venue", ""),
        sides=sides,
    )


def normalize_markets(
    meta: dict[str, Any], mids: dict[str, str]
) -> list[OutcomeMarket]:
    """Normalize all outcomes, isolating failures per market.

    One malformed market is logged and skipped; it must never prevent
    the other 41 from being served.
    """
    markets: list[OutcomeMarket] = []
    for raw in meta.get("outcomes", []):
        try:
            markets.append(normalize_outcome(raw, mids))
        except Exception:
            logger.exception(
                "Skipping unnormalizable outcome: %r", raw.get("outcome")
            )
    return markets


if __name__ == "__main__":
    # Standalone verification: full pipeline against live mainnet.
    import asyncio

    import httpx

    from app.services.hyperliquid import HyperliquidClient

    async def main() -> None:
        async with httpx.AsyncClient() as http:
            client = HyperliquidClient(http)
            meta = await client.fetch_outcome_meta()
            mids = await client.fetch_all_mids()

        markets = normalize_markets(meta, mids)
        raw_count = len(meta.get("outcomes", []))
        print(f"normalized {len(markets)} of {raw_count} outcomes\n")

        for m in markets[:3]:
            print(m.model_dump_json(by_alias=True, indent=2))

        fallbacks = [m for m in markets if m.question == m.description]
        no_close = [m for m in markets if m.closes_at is None]
        priced = [
            m for m in markets if all(s.price is not None for s in m.sides)
        ]
        pair_ok = sum(
            1
            for m in priced
            if len(m.sides) == 2
            and abs(m.sides[0].price + m.sides[1].price - 1.0) < 0.001
        )
        print(f"\nquestion fell back to raw description: {len(fallbacks)}")
        for m in fallbacks[:5]:
            print(f"  - {m.id} {m.name}: {m.description[:70]}")
        print(f"missing closesAt: {len(no_close)}")
        print(f"fully priced: {len(priced)}; price pairs summing to ~1: {pair_ok}")

    asyncio.run(main())