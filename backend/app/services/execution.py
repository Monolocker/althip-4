"""Execution costs: what buying N contracts would really cost (22.4).

Pure functions only. Each venue's book arrives here already sorted
BEST FIRST, as (price, size) pairs: the adapters own the venue-specific
quirks (Polymarket's best-last lists, Kalshi's No-bid asks).

Fee models, all read from live parameters, never hard-coded rates:
  - Hyperliquid (official fee docs, "Outcome tokens"): no fee to open;
    fees when closing or settling. At settlement the fee-bearing volume
    is settle_fraction * size, so holding to a WIN costs taker_rate * size
    and holding to a loss costs nothing.
  - Polymarket (docs + Gamma "feeSchedule"): takers pay
    size * rate * (p * (1 - p)) ** exponent; makers pay nothing.
  - Kalshi (fee schedule; series "fee_type"/"fee_multiplier"): takers
    pay 0.07 * multiplier * size * p * (1 - p), ROUNDED UP to the cent
    per order.
"""

import math
from dataclasses import dataclass
from datetime import datetime

from app.models.costs import VenueCost
from app.models.venue import MatchLevel

Levels = list[tuple[float, float]]  # (price, size), best first

KALSHI_TAKER_COEFFICIENT = 0.07
KALSHI_QUADRATIC_TYPES = {"quadratic", "quadratic_with_maker_fees"}


@dataclass(frozen=True)
class Walk:
    fills: Levels  # (price, size) actually taken, best first
    filled: float
    unfilled: float
    average_price: float | None


def walk_book(asks: Levels, size: float) -> Walk:
    """Fill `size` contracts against best-first asks, level by level.

    Liquidity and slippage in one loop: each level supplies at most its
    resting size; whatever no level can supply is `unfilled`.
    """
    remaining = size
    fills: Levels = []
    for price, available in asks:
        if remaining <= 0:
            break
        take = min(available, remaining)
        fills.append((price, take))
        remaining -= take
    filled = size - remaining
    average = sum(p * s for p, s in fills) / filled if filled > 0 else None
    return Walk(fills=fills, filled=filled, unfilled=max(0.0, remaining), average_price=average)


def _assemble(
    *,
    venue,
    external_id: str | None,
    title: str,
    match_level: MatchLevel | None,
    asks: Levels,
    bids: Levels,
    walk: Walk,
    fee_now: float,
    fee_if_wins: float,
    fee_basis: str,
    warnings: list[str],
    book_time: datetime | None,
) -> VenueCost:
    best_ask = asks[0][0] if asks else None
    best_bid = bids[0][0] if bids else None
    mid = (best_ask + best_bid) / 2 if best_ask is not None and best_bid is not None else None
    cost = (
        (walk.average_price * walk.filled + fee_now) / walk.filled
        if walk.average_price is not None and walk.filled > 0
        else None
    )
    win_fee_per_contract = fee_if_wins / walk.filled if walk.filled > 0 else 0.0
    break_even = cost / (1 - win_fee_per_contract) if cost is not None else None
    if walk.unfilled > 0:
        warnings = [
            *warnings,
            f"Book too thin: only {walk.filled:,.0f} of {walk.filled + walk.unfilled:,.0f} "
            "contracts available at any price",
        ]
    return VenueCost(
        venue=venue,
        external_id=external_id,
        title=title,
        match_level=match_level,
        filled=walk.filled,
        unfilled=walk.unfilled,
        best_ask=best_ask,
        mid=mid,
        average_price=walk.average_price,
        slippage=(walk.average_price - best_ask)
        if walk.average_price is not None and best_ask is not None
        else None,
        fee_now=round(fee_now, 6),
        fee_if_wins=round(fee_if_wins, 6),
        cost_per_contract=cost,
        break_even=break_even,
        fee_basis=fee_basis,
        warnings=warnings,
        book_time=book_time,
    )


def deployer_fee_factor(scale: float) -> float:
    """How a market's deployerFeeScale multiplies Hyperliquid's fees.

    Hyperliquid's published formula (the HIP-3 branch): x(scale + 1)
    below 1, x(2 * scale) from 1; scale 0 leaves fees unchanged.
    Verified for outcomes in the 23 probe: `out` markets (scale 1.0)
    charged a median 14 bps at settlement, twice the 7 bps base rate.
    """
    return scale + 1 if scale < 1 else 2 * scale


def hyperliquid_cost(
    *,
    title: str,
    asks: Levels,
    bids: Levels,
    size: float,
    taker_rate: float,
    deployer_fee_scale: float,
    book_time: datetime | None,
) -> VenueCost:
    walk = walk_book(asks, size)
    rate = taker_rate * deployer_fee_factor(deployer_fee_scale)
    scale_note = (
        f" (base {taker_rate * 10_000:g} bps x{deployer_fee_factor(deployer_fee_scale):g} "
        f"for deployerFeeScale {deployer_fee_scale:g})"
        if deployer_fee_scale > 0
        else ""
    )
    return _assemble(
        venue="hyperliquid",
        external_id=None,
        title=title,
        match_level=None,
        asks=asks,
        bids=bids,
        walk=walk,
        fee_now=0.0,
        fee_if_wins=rate * walk.filled,  # settle_fraction 1 on a win
        fee_basis=(
            f"No fee to open; {rate * 10_000:g} bps on the payout at settlement, "
            f"only if it wins{scale_note} (base tier)"
        ),
        warnings=[],
        book_time=book_time,
    )


def polymarket_cost(
    *,
    external_id: str,
    title: str,
    match_level: MatchLevel | None,
    asks: Levels,
    bids: Levels,
    size: float,
    rate: float,
    exponent: float,
    min_order_size: float | None,
    book_time: datetime | None,
) -> VenueCost:
    walk = walk_book(asks, size)
    fee = sum(s * rate * (p * (1 - p)) ** exponent for p, s in walk.fills)
    warnings = []
    if min_order_size is not None and size < min_order_size:
        warnings.append(f"Below Polymarket's minimum order of {min_order_size:g} contracts")
    return _assemble(
        venue="polymarket",
        external_id=external_id,
        title=title,
        match_level=match_level,
        asks=asks,
        bids=bids,
        walk=walk,
        fee_now=fee,
        fee_if_wins=0.0,
        fee_basis=(
            f"Taker fee: size x {rate:g} x p(1-p)" + (f"^{exponent:g}" if exponent != 1 else "")
            if rate > 0
            else "No trading fee on this market"
        ),
        warnings=warnings,
        book_time=book_time,
    )


def kalshi_cost(
    *,
    external_id: str,
    title: str,
    match_level: MatchLevel | None,
    asks: Levels,
    bids: Levels,
    size: float,
    fee_type: str,
    fee_multiplier: float,
    book_time: datetime | None,
) -> VenueCost:
    walk = walk_book(asks, size)
    warnings = []
    if fee_type in KALSHI_QUADRATIC_TYPES:
        raw = sum(KALSHI_TAKER_COEFFICIENT * fee_multiplier * s * p * (1 - p) for p, s in walk.fills)
        # Rounded UP to the cent, per order. round(…, 6) first strips
        # float noise (6.7300000001 must not become 6.74).
        fee = math.ceil(round(raw * 100, 6)) / 100
        basis = f"Taker fee: {KALSHI_TAKER_COEFFICIENT * fee_multiplier:g} x size x p(1-p), rounded up to the cent"
    else:
        fee = 0.0
        basis = f"Unknown fee type {fee_type!r}"
        warnings.append(f"Kalshi fee type {fee_type!r} is not modelled; the fee shown is 0")
    return _assemble(
        venue="kalshi",
        external_id=external_id,
        title=title,
        match_level=match_level,
        asks=asks,
        bids=bids,
        walk=walk,
        fee_now=fee,
        fee_if_wins=0.0,
        fee_basis=basis,
        warnings=warnings,
        book_time=book_time,
    )