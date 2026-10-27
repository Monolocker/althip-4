"""Backend analytics: application-specific summaries (Milestone 20).

Pure functions over data the app already has (the normalized snapshot):
no I/O, no clock reads. `now` is passed in, so every result is
reproducible from its inputs, the same rule as MarketData.as_of (18.3b).
"""

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from app.models.deployers import DeployerStats, QualityCounts
from app.models.market import OutcomeMarket


def _operator_count(deployer: dict[str, Any] | None) -> int:
    """Distinct addresses across a deployer's subDeployers permission lists.

    Raw shape (17.4 probe): [[action, [address, ...]], ...]. Parsed
    defensively: anything unexpected simply counts as no operators.
    """
    if deployer is None:
        return 0
    addresses: set[str] = set()
    for entry in deployer.get("subDeployers") or []:
        if isinstance(entry, list) and len(entry) == 2 and isinstance(entry[1], list):
            addresses.update(str(address) for address in entry[1])
    return len(addresses)


def _summarize(
    venue: str,
    markets: list[OutcomeMarket],
    deployer: dict[str, Any] | None,
    now: datetime,
) -> DeployerStats:
    quality = QualityCounts()
    for market in markets:
        key = market.book.quality if market.book is not None else "unknown"
        setattr(quality, key, getattr(quality, key) + 1)

    upcoming = [
        time
        for market in markets
        if (time := market.event_at or market.resolves_by) is not None
        and time > now
    ]
    traded = [m for m in markets if (m.volume_24h or 0) > 0]
    top = max(traded, key=lambda m: m.volume_24h or 0, default=None)

    return DeployerStats(
        venue=venue,
        address=deployer.get("deployer") if deployer else None,
        operator_count=_operator_count(deployer),
        market_count=len(markets),
        question_count=len({m.parent.id for m in markets if m.parent is not None}),
        volume_24h=sum(m.volume_24h or 0 for m in markets),
        book_quality=quality,
        categories=dict(Counter(m.category or "uncategorized" for m in markets)),
        next_event_at=min(upcoming, default=None),
        top_market_id=top.id if top else None,
        top_market_question=top.question if top else None,
    )


def deployer_stats(
    markets: list[OutcomeMarket],
    meta: dict[str, Any],
    now: datetime,
) -> list[DeployerStats]:
    """One summary per deployer, busiest (by 24h volume) first.

    Includes deployers listed in outcomeMeta that currently have no live
    markets, so the directory shows every venue, not just active ones.
    """
    by_venue: dict[str, list[OutcomeMarket]] = defaultdict(list)
    for market in markets:
        by_venue[market.venue].append(market)

    deployers = {
        str(d.get("venue")): d
        for d in meta.get("deployers", [])
        if isinstance(d, dict) and d.get("venue") is not None
    }

    stats = [
        _summarize(venue, by_venue.get(venue, []), deployers.get(venue), now)
        for venue in set(by_venue) | set(deployers)
    ]
    # Iterating a set has no guaranteed order, so ties must be broken
    # explicitly or the directory would reshuffle between requests:
    # volume, then market count, then venue name.
    stats.sort(key=lambda s: (-s.volume_24h, -s.market_count, s.venue))
    return stats