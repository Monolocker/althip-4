"""Backend analytics: application-specific summaries (Milestone 20).

Pure functions over data the app already has (the normalized snapshot):
no I/O, no clock reads. `now` is passed in, so every result is
reproducible from its inputs, the same rule as MarketData.as_of (18.3b).
"""

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from app.models.deployers import DeployerStats, QualityCounts
from app.models.market import Lookalike, OutcomeMarket, SpecDifference
from app.services.normalize import (
    display_spec_value,
    parse_spec,
    questions_by_outcome,
)


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


# ---------------------------------------------------------------
# Lookalikes (Milestone 20.3)
# ---------------------------------------------------------------


def find_lookalikes(
    markets: list[OutcomeMarket],
    meta: dict[str, Any],
) -> dict[str, list[Lookalike]]:
    """For each market, the other live markets with its exact title but
    different spec values, i.e. different resolution rules.

    Found in the 20.3 probe: all three Anthropic IPO ladders (skew, out,
    txyz) share titles like "Anthropic first-day market cap above $1500B?"
    but have listing deadlines months apart. Markets with identical spec
    (true duplicates) are not lookalikes: their rules are identical.
    """
    questions = questions_by_outcome(meta)

    def spec_values(market: OutcomeMarket) -> dict[str, str]:
        # Same merge as rendering: question spec, overridden by own spec.
        question = questions.get(int(market.id))
        question_spec = (
            parse_spec(question.get("description", "")) if question else {}
        )
        return {**question_spec, **parse_spec(market.description)}

    by_title: dict[str, list[OutcomeMarket]] = defaultdict(list)
    for market in markets:
        by_title[market.question].append(market)

    result: dict[str, list[Lookalike]] = {}
    for group in by_title.values():
        if len(group) < 2:
            continue
        specs = {market.id: spec_values(market) for market in group}
        for market in group:
            mine = specs[market.id]
            refs: list[Lookalike] = []
            for other in group:
                if other.id == market.id:
                    continue
                theirs = specs[other.id]
                differing = sorted(
                    key
                    for key in set(mine) | set(theirs)
                    if mine.get(key) != theirs.get(key)
                )
                if not differing:
                    continue  # identical rules: a duplicate, not a lookalike
                refs.append(
                    Lookalike(
                        market_id=other.id,
                        venue=other.venue,
                        differences=[
                            SpecDifference(
                                key=key,
                                this_value=(
                                    display_spec_value(key, mine[key])
                                    if key in mine
                                    else "—"
                                ),
                                other_value=(
                                    display_spec_value(key, theirs[key])
                                    if key in theirs
                                    else "—"
                                ),
                            )
                            for key in differing
                        ],
                    )
                )
            if refs:
                result[market.id] = refs
    return result