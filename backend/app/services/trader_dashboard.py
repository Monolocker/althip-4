"""One trader's HIP-4 dashboard (Milestone 26.2).

Two halves, kept apart on purpose:
  - STORED: stats, the PnL chart and resolved markets for a window,
    computed from stored fills with the leaderboard's definitions (26.1).
    Blocking SQLite work: call compute_stored through asyncio.to_thread.
  - LIVE: positions and open orders, read from Hyperliquid per request
    (26.0 probes: outcome balances are spotClearinghouseState balances
    named "+N" for the coin "#N"; open orders come from
    frontendOpenOrders with "#N" coins). build_positions and
    build_orders only normalize those raw shapes.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.leaderboard import LeaderboardWindow
from app.models.market import OutcomeMarket, OutcomeSide
from app.models.trader import (
    BiggestWin,
    PnlPoint,
    ResolvedMarket,
    TraderOrder,
    TraderPosition,
    TraderPositions,
    TraderStats,
)
from app.services.leaderboard import LAG_TOLERANCE_MS, WINDOW_SPANS_MS
from app.services.traders import TraderStore

MINUTE_MS = 60_000
HOUR_MS = 60 * MINUTE_MS
DAY_MS = 24 * HOUR_MS

# Chart resolution per window: about 100-180 points, whatever the
# trader's activity, so a market maker's 100,000 fills stay a small payload.
BUCKET_MS: dict[LeaderboardWindow, int] = {
    "24h": 15 * MINUTE_MS,
    "7d": HOUR_MS,
    "30d": 4 * HOUR_MS,
    "all": DAY_MS,
}

# A side's coin "#N" -> (market, side) in the live snapshot.
SideIndex = dict[str, tuple[OutcomeMarket, OutcomeSide]]


def _utc(ms: int) -> datetime:
    """Epoch milliseconds -> UTC datetime. Every caller has a real time."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _num(value: Any) -> float | None:
    """Hyperliquid sends numbers as strings; anything unreadable is None."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_complete(
    coverage_from: int | None, fills_through: int | None, last_trade_at: int, start: int | None
) -> bool:
    """The leaderboard's COMPLETE rule (traders.py), for one trader.

    Kept in step with the SQL by a test: a trader the leaderboard ranks
    must be complete here, and the other way round.
    """
    return (
        coverage_from is not None
        and fills_through is not None
        and fills_through >= last_trade_at - LAG_TOLERANCE_MS
        and (start is None or coverage_from <= start)
    )


@dataclass(frozen=True)
class StoredPart:
    window_start: int | None
    complete: bool
    history_from: int | None
    fills_through: int | None
    stats: TraderStats
    biggest_win: BiggestWin | None
    pnl_series: list[PnlPoint]
    resolved: list[ResolvedMarket]


def compute_stored(
    store: TraderStore, address: str, window: LeaderboardWindow, now_ms: int
) -> StoredPart | None:
    """The window half of the dashboard; None if the address is unknown."""
    row = store.trader(address)
    if row is None:
        return None
    coverage_from, fills_through, last_trade_at = row
    span = WINDOW_SPANS_MS[window]
    window_start = None if span is None else now_ms - span
    complete = is_complete(coverage_from, fills_through, last_trade_at, window_start)

    # Figures start where the stored history is proven, never earlier:
    # the window start, or the trader's coverage start if that is later
    # (All-Time: always the coverage start). Unknown coverage: from the
    # window start (or every stored fill), shown with complete = False.
    start = window_start if window_start is not None else (coverage_from or 0)
    if coverage_from is not None and coverage_from > start:
        start = coverage_from
    history_from = start if start > 0 else None

    markets = store.trader_markets(address, start)
    bucket = BUCKET_MS[window]
    buckets = store.trader_pnl_buckets(address, start, bucket)

    wins = losses = 0
    resolved: list[ResolvedMarket] = []
    best: dict[str, Any] | None = None
    for market in markets:
        net = market["gross_pnl"] - market["fees"]
        if market["realized"]:
            result = "win" if net > 0 else "loss" if net < 0 else "even"
            wins += result == "win"
            losses += result == "loss"
            resolved.append(
                ResolvedMarket(
                    market_id=str(market["outcome"]),
                    title=market["title"],
                    net_pnl=net,
                    fees=market["fees"],
                    volume=market["volume"],
                    result=result,
                    settled=bool(market["settled"]),
                    last_fill_at=_utc(market["last_fill"]),
                )
            )
        if net > 0 and (best is None or net > best["gross_pnl"] - best["fees"]):
            best = market
    resolved.sort(key=lambda item: item.last_fill_at, reverse=True)

    gross = sum(market["gross_pnl"] for market in markets)
    fees = sum(market["fees"] for market in markets)
    stats = TraderStats(
        net_pnl=gross - fees,
        gross_pnl=gross,
        fees=fees,
        volume=sum(market["volume"] for market in markets),
        markets=len(markets),
        wins=wins,
        losses=losses,
        accuracy=wins / (wins + losses) if wins + losses else None,
    )
    biggest_win = (
        BiggestWin(
            market_id=str(best["outcome"]),
            title=best["title"],
            net_pnl=best["gross_pnl"] - best["fees"],
        )
        if best is not None
        else None
    )

    # A step chart: 0 at the start, then the running total at the end of
    # every bucket that had fills (capped at now for the last bucket).
    chart_start = start if start > 0 else (buckets[0][0] * bucket if buckets else now_ms)
    series = [PnlPoint(time=_utc(chart_start), pnl=0.0)]
    total = 0.0
    for number, net in buckets:
        total += net
        series.append(PnlPoint(time=_utc(min(start + (number + 1) * bucket, now_ms)), pnl=total))
    # Flat to now: a quiet stretch at the end is part of the window too.
    if series[-1].time < _utc(now_ms):
        series.append(PnlPoint(time=_utc(now_ms), pnl=total))

    return StoredPart(
        window_start=window_start,
        complete=complete,
        history_from=history_from,
        fills_through=fills_through,
        stats=stats,
        biggest_win=biggest_win,
        pnl_series=series,
        resolved=resolved,
    )


def side_index(markets: list[OutcomeMarket]) -> SideIndex:
    return {side.coin: (market, side) for market in markets for side in market.sides}


def build_positions(balances: list[dict[str, Any]], sides: SideIndex) -> TraderPositions:
    """Outcome balances ("+N") in markets that are still live.

    A balance whose coin is not in the live snapshot is left out: its
    market has settled (or is unknown), and settled results belong in
    the resolved list, from fills.
    """
    items: list[TraderPosition] = []
    for balance in balances:
        name = str(balance.get("coin", ""))
        if not name.startswith("+") or not name[1:].isdigit():
            continue
        coin = "#" + name[1:]
        shares = _num(balance.get("total")) or 0.0
        match = sides.get(coin)
        if match is None or shares == 0:
            continue
        market, side = match
        price = side.price
        items.append(
            TraderPosition(
                coin=coin,
                market_id=market.id,
                title=market.question,
                side_label=side.label,
                shares=shares,
                on_hold=_num(balance.get("hold")) or 0.0,
                entry_notional=_num(balance.get("entryNtl")),
                price=price,
                value=shares * price if price is not None else None,
            )
        )
    # Priced positions by value, biggest first; unpriced ones after them.
    items.sort(key=lambda item: (item.value is None, -(item.value or 0.0), -item.shares))
    priced = [item for item in items if item.value is not None]
    return TraderPositions(
        value=sum(item.value or 0.0 for item in priced),
        unpriced=len(items) - len(priced),
        count=len(items),
        biggest=priced[0] if priced else None,
        items=items,
    )


def build_orders(raw: list[dict[str, Any]], sides: SideIndex) -> list[TraderOrder]:
    """Resting outcome orders ("#N" coins), newest first."""
    orders: list[TraderOrder] = []
    for order in raw:
        coin = str(order.get("coin", ""))
        if not coin.startswith("#") or not coin[1:].isdigit():
            continue
        price, size, timestamp = _num(order.get("limitPx")), _num(order.get("sz")), _num(order.get("timestamp"))
        if price is None or size is None or timestamp is None:
            continue
        match = sides.get(coin)
        orders.append(
            TraderOrder(
                coin=coin,
                market_id=match[0].id if match else str(int(coin[1:]) // 10),
                title=match[0].question if match else None,
                side_label=match[1].label if match else None,
                direction="buy" if order.get("side") == "B" else "sell",
                price=price,
                size=size,
                original_size=_num(order.get("origSz")) or size,
                placed_at=_utc(int(timestamp)),
                order_type=order.get("orderType"),
                tif=order.get("tif"),
                reduce_only=bool(order.get("reduceOnly", False)),
            )
        )
    orders.sort(key=lambda item: item.placed_at, reverse=True)
    return orders