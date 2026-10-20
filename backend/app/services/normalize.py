"""Normalization layer: Raw HL data -> app domain model"""

import logging 
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from app.models.market import (
    BookSummary,
    OutcomeMarket, 
    OutcomeMarketDetail,
    OutcomeSide,
    QuestionMembership,
    Settlement,
)

from app.models.book import BookLevel, OrderBook


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TopOfBook:
    """Best bid and ask of one coin, as recorded by the book sweep"""

    bid: float | None
    ask: float | None
    checked_at: float # time.time() when the book was fetched


@dataclass(frozen=True)
class MarketData:
    """Everything fetched from Hyperliquid that normalization reads.

    One object instead of four parameters threaded through every function
    (Milestone 18.3a). Adding a new input means adding a field here, not
    changing every signature between the snapshot and normalize_outcome.
    frozen=True: a snapshot's data never changes after it is built.
    """

    meta: dict[str, Any]
    mids: dict[str, str] = field(default_factory=dict)
    ctxs: dict[str, dict[str, Any]] = field(default_factory=dict)
    templates: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Side-0 top of book per coin, from the background sweep (18.3b)
    tops: dict[str, TopOfBook] = field(default_factory=dict)
    # When this data was assembled (time.time()). Book ages are measured
    # against it, which keeps normalization a pure function of its input
    as_of: float = 0.0

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
    
# Spec keys that carry times, in priority order. Hyperliquid's docs do
# not define template fields: these meanings are inferred from key names
# and observed live values (Milestone 17.2 investigation).
# Event keys: when the deciding thing happens.
EVENT_TIME_KEYS = ("time", "expiry", "scheduledStart", "scheduledDecision")
# Deadline keys: the latest time the market should resolve.
DEADLINE_KEYS = (
    "resolutionDeadline",
    "decisionDeadline",
    "listingDeadline",
    "dateTime",
)


def _first_time(spec: dict[str, str], keys: tuple[str, ...]) -> datetime | None:
    """Return the first key in `keys` whose value parses as a timestamp."""
    for key in keys:
        raw = spec.get(key)
        if raw:
            parsed = parse_hl_timestamp(raw)
            if parsed is not None:
                return parsed
    return None


def resolve_times(
    spec: dict[str, str],
) -> tuple[datetime | None, datetime | None]:
    """Find (event_at, resolves_by) in a parsed spec.

    Price markets have one time that is both the event and the deadline,
    so resolves_by falls back to event_at.
    """
    event_at = _first_time(spec, EVENT_TIME_KEYS)
    resolves_by = _first_time(spec, DEADLINE_KEYS) or event_at
    return event_at, resolves_by


def questions_by_outcome(meta: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Map each question member's outcome id to its raw parent question.

    Multi-outcome question members (e.g. "participant:Buffalo Bills")
    carry neither times nor a readable title of their own; the question
    they belong to does.
    """
    index: dict[int, dict[str, Any]] = {}
    for question in meta.get("questions", []):
        members = [*question.get("namedOutcomes", []), question.get("fallbackOutcome")]
        for member in members:
            try:
                index[int(member)] = question
            except (TypeError, ValueError):
                # None (no fallback outcome) or a malformed id: skip it.
                continue
    return index


# ---------------------------------------------------------------
# Templates (Milestone 18.1)
# ---------------------------------------------------------------
# Every deployer-created market comes from a validator-approved template
# whose `name` is a display title with {placeholders}, e.g.
# "{perp} above {threshold} at {time}?". Filling those placeholders with
# the market's own spec values gives Hyperliquid's approved wording
# instead of wording we invented.

PLACEHOLDER = re.compile(r"\{(\w+)\}")

# Placeholder values in HL's YYYYMMDD-HHMM format get rendered readably.
TIMESTAMP_KEYS = frozenset((*EVENT_TIME_KEYS, *DEADLINE_KEYS))

# Outcomes the protocol creates for each question ("other"); they have
# no template of their own.
FALLBACK_OUTCOME_NAME = "template fallback"

# Template descriptions end with machine-readable metadata, e.g.
# "metadata=category:sports|subCategory:Basketball|semanticRestriction:..."
# It describes the template, not the market's rules, so it is cut from
# the displayed rules.
METADATA_MARKER = "metadata="


def index_templates(raw: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """outcomeTemplates list -> {template id: template}."""
    return {
        str(t["id"]): t for t in raw if isinstance(t, dict) and "id" in t
    }


def template_id(name: str) -> str | None:
    """'template:binaryPrice' -> 'binaryPrice'; non-template names -> None."""
    prefix = "template:"
    return name[len(prefix):] if name.startswith(prefix) else None


def _format_value(key: str, value: str, add_utc: bool) -> str:
    if key in TIMESTAMP_KEYS:
        parsed = parse_hl_timestamp(value)
        if parsed is not None:
            suffix = " UTC" if add_utc else ""
            return parsed.strftime("%b %d, %Y %H:%M") + suffix
    return value


def render_template(text: str, values: dict[str, str]) -> str | None:
    """Fill every {placeholder} in `text` from `values`.

    All or nothing: if any placeholder has no value, return None so the
    caller falls back, rather than showing a half-filled "{shortNameA}".
    """
    keys = PLACEHOLDER.findall(text)
    if any(key not in values for key in keys):
        return None

    def substitute(match: re.Match[str]) -> str:
        # Some templates already write "{scheduledStart} UTC"; adding our
        # own suffix there would produce "... 17:00 UTC UTC".
        already_labeled = text.startswith(" UTC", match.end())
        key = match.group(1)
        return _format_value(key, values[key], add_utc=not already_labeled)

    return PLACEHOLDER.sub(substitute, text)


def _lookup_template(
    name: str, templates: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    tid = template_id(name)
    return templates.get(tid) if tid is not None else None


def _question_title(
    question: dict[str, Any] | None,
    question_spec: dict[str, str],
    templates: dict[str, dict[str, Any]],
) -> str | None:
    """Rendered title of a parent question, e.g. 'NBA Week 1: Spurs v Suns'."""
    if question is None:
        return None
    template = _lookup_template(question.get("name", ""), templates)
    if template is None:
        return None
    return render_template(template.get("name", ""), question_spec)


def template_question(
    name: str,
    values: dict[str, str],
    question: dict[str, Any] | None,
    question_spec: dict[str, str],
    templates: dict[str, dict[str, Any]],
) -> str | None:
    """Display title from the market's template, or None to fall back.

    A question member's own title is only part of the story ("Draw"), so
    it is joined with its parent question's title.
    """
    if name == FALLBACK_OUTCOME_NAME:
        parent = _question_title(question, question_spec, templates)
        # Labeled "Fallback", not "Other": some questions also have a named
        # outcome called "Other" (awardOther), and the two must not look alike.
        return f"Fallback — {parent}" if parent is not None else None

    template = _lookup_template(name, templates)
    if template is None:
        return None
    own = render_template(template.get("name", ""), values)
    if own is None:
        return None

    role = template.get("role")
    if isinstance(role, dict) and "questionOutcome" in role:
        parent = _question_title(question, question_spec, templates)
        return f"{own} — {parent}" if parent is not None else own
    return own


def template_rules(
    name: str, values: dict[str, str], templates: dict[str, dict[str, Any]]
) -> str | None:
    """A market's resolution rules: its template's description, filled in."""
    template = _lookup_template(name, templates)
    if template is None:
        return None
    rules = render_template(template.get("description", ""), values)
    if rules is None:
        return None
    # partition() splits at the first marker; text after it is metadata.
    before, _, _ = rules.partition(METADATA_MARKER)
    return before.rstrip() or None


def template_side_names(
    name: str, values: dict[str, str], templates: dict[str, dict[str, Any]]
) -> list[str] | None:
    """Rendered side names for standalone markets, e.g. ["SAS", "PHX"].

    The template defines what each side means: for sportsContestWinner,
    side 0 is {shortNameA} and side 1 is {shortNameB}, not Yes/No.
    """
    template = _lookup_template(name, templates)
    if template is None:
        return None
    role = template.get("role")
    if not isinstance(role, dict):
        return None
    standalone = role.get("standaloneOutcome")
    if not isinstance(standalone, dict):
        return None
    side_names = standalone.get("sideNames")
    if not isinstance(side_names, list):
        return None
    rendered = [render_template(str(side), values) for side in side_names]
    if any(label is None for label in rendered):
        return None
    return [label for label in rendered if label is not None]


def index_outcome_ctxs(ctxs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Keep only outcome coins ("#...") from spotMetaAndAssetCtxs, keyed by coin.

    The same response also carries ~400 ordinary spot pairs; we only need
    outcome coins, and a dict gives O(1) lookup per market side.
    """
    return {
        str(ctx["coin"]): ctx
        for ctx in ctxs
        if isinstance(ctx, dict) and str(ctx.get("coin", "")).startswith("#")
    }


def _parse_volume(ctx: dict[str, Any] | None) -> float | None:
    """Read dayBaseVlm defensively: missing or malformed means unknown."""
    if ctx is None:
        return None
    try:
        return float(ctx["dayBaseVlm"])
    except (KeyError, TypeError, ValueError):
        return None

# ---------------------------------------------------------------
# Book quality (Milestone 18.3b)
# ---------------------------------------------------------------
# Thresholds chosen in 18.3 from the full-book probe: 156 markets were
# within 2c, 31 between 2c and 10c, 144 empty, one-sided or wider.
TIGHT_MAX_SPREAD = 0.02
WIDE_MAX_SPREAD = 0.10
# Sweep data older than this is not trusted (the sweep may have stalled).
# 2.5 sweep intervals of 180s: one missed sweep is tolerated, two are not.
TOP_MAX_AGE_SECONDS = 450.0
# Hyperliquid's mark for a coin that has never traded. Observed in 18.3:
# 106 of 106 markets with this mark had an unusable book.
PLACEHOLDER_MARK = "0.5"


def classify_spread(
    bid: float | None, ask: float | None
) -> tuple[float | None, str]:
    """(spread, quality) for a top of book.

    The spread is rounded to 6 decimals before comparing: in floating
    point 0.30 - 0.28 is 0.020000000000000018, which would wrongly fail
    a "<= 0.02" check.
    """
    if bid is None or ask is None:
        return None, "unreliable"
    spread = round(ask - bid, 6)
    if spread <= TIGHT_MAX_SPREAD:
        return spread, "tight"
    if spread <= WIDE_MAX_SPREAD:
        return spread, "wide"
    return spread, "unreliable"


def book_summary(coin: str, data: MarketData) -> BookSummary | None:
    """Book quality for one coin: fresh sweep data first, cheap signal second."""
    top = data.tops.get(coin)
    if top is not None and data.as_of - top.checked_at <= TOP_MAX_AGE_SECONDS:
        spread, quality = classify_spread(top.bid, top.ask)
        return BookSummary(
            quality=quality,
            source="sweep",
            bid=top.bid,
            ask=top.ask,
            spread=spread,
            checked_at=datetime.fromtimestamp(top.checked_at, tz=timezone.utc),
        )

    # Fallback: the placeholder mark can only ever say "unreliable". It
    # never claims a market is tight, so it never greys out a real price.
    ctx = data.ctxs.get(coin)
    if ctx is not None and ctx.get("markPx") == PLACEHOLDER_MARK:
        return BookSummary(quality="unreliable", source="mark")
    return None


def clean_label(label: str) -> str:
    """'template:Yes' -> 'Yes'"""
    prefix = "template:"
    return label[len(prefix):] if label.startswith(prefix) else label

def _fmt_time(dt: datetime | None) -> str:
    return dt.strftime("%b %d, %Y %H:%M UTC") if dt else "expiry"

def build_question(name: str, spec: dict[str, str], event_at: datetime | None) -> str | None:
    """Build a human-readable display summary for known dialects
    
    Returns None for unknown dialects so the caller can fall back
    to the raw description. These strings are display text only,
    exact resolution semantics live in HL's own rules
    """
    when = _fmt_time(event_at)

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
    raw: dict[str, Any],
    data: MarketData,
    question: dict[str, Any] | None = None,
) -> OutcomeMarket:
    """Convert one raw Hyperliquid outcome into our model.

    `question` is the raw parent question this outcome belongs to, if
    any; it supplies times and title text the outcome itself lacks.
    From `data`: mids give prices, ctxs give volume (a missing coin
    leaves it unknown), templates give approved display wording (without
    them, titles fall back to build_question or the raw spec).
    """
    outcome_id = int(raw["outcome"])
    description = raw.get("description", "")
    spec = parse_spec(description)
    question_spec = (
        parse_spec(question.get("description", "")) if question else {}
    )

    # Outcome keys override question keys: the more specific spec wins.
    values = {**question_spec, **spec}
    event_at, resolves_by = resolve_times(values)

    name = raw.get("name", "")
    templates = data.templates
    title = (
        template_question(name, values, question, question_spec, templates)
        or build_question(name, spec, event_at)
        or description
        or name
    )
    side_names = template_side_names(name, values, templates)

    sides: list[OutcomeSide] = []
    for index, side_spec in enumerate(raw.get("sideSpecs", [])[:2]):
        coin = f"#{10 * outcome_id + index}"
        raw_mid = data.mids.get(coin)
        try:
            price = float(raw_mid) if raw_mid is not None else None
        except ValueError:
            price = None
        sides.append(
            OutcomeSide(
                index=index,
                label=(
                    side_names[index]
                    if side_names is not None and index < len(side_names)
                    else clean_label(side_spec.get("name", f"Side {index}"))
                ),
                coin=coin,
                price=price,
            )
        )
    yes_coin = f"#{10 * outcome_id}"
    volume_24h = _parse_volume(data.ctxs.get(yes_coin))

    return OutcomeMarket(
        id=str(outcome_id),
        name=name,
        question=title,
        description=description,
        status="open",
        event_at=event_at,
        resolves_by=resolves_by,
        quote_token=raw.get("quoteToken", "USDC"),
        venue=raw.get("venue", ""),
        sides=sides,
        volume_24h=volume_24h,
        book=book_summary(yes_coin, data)
    )


def normalize_markets(data: MarketData) -> list[OutcomeMarket]:
    """Normalize all outcomes, isolating failures per market.

    One malformed market is logged and skipped; it must never prevent
    the other 41 from being served.
    """
    questions = questions_by_outcome(data.meta)
    markets: list[OutcomeMarket] = []
    for raw in data.meta.get("outcomes", []):
        try:
            question = questions.get(int(raw["outcome"]))
            markets.append(normalize_outcome(raw, data, question))
        except Exception:
            logger.exception(
                "Skipping unnormalizable outcome: %r", raw.get("outcome")
            )
    return markets

def find_question_membership(
    outcome_id: int,
    meta: dict[str, Any],
    templates: dict[str, dict[str, Any]] | None = None,
) -> QuestionMembership | None:
    """Find the question this outcome belongs to, if any.

    Questions reference their outcomes by id (namedOutcomes plus a
    fallbackOutcome); outcomes do not point back at their question,
    so we search from the question side.
    """
    templates = templates or {}
    for question in meta.get("questions", []):
        named = [int(x) for x in question.get("namedOutcomes", [])]
        fallback = question.get("fallbackOutcome")
        fallback_id = int(fallback) if fallback is not None else None
        members = named + ([fallback_id] if fallback_id is not None else [])

        if outcome_id in members:
            question_spec = parse_spec(question.get("description", ""))
            return QuestionMembership(
                question_id=str(question.get("question")),
                name=question.get("name", ""),
                description=question.get("description", ""),
                is_fallback=(outcome_id == fallback_id),
                sibling_ids=[str(m) for m in members if m != outcome_id],
                title=_question_title(question, question_spec, templates),
                rules=template_rules(
                    question.get("name", ""), question_spec, templates
                ),
            )
    return None


def find_deployer(venue: str, meta: dict[str, Any]) -> str | None:
    """Look up the deployer address for a venue from outcomeMeta."""
    for deployer in meta.get("deployers", []):
        if deployer.get("venue") == venue:
            return deployer.get("deployer")
    return None


def _build_detail(
    base: OutcomeMarket,
    data: MarketData,
    settlement: Settlement | None = None,
) -> OutcomeMarketDetail:
    """Assemble the detail model from a base market plus derived data."""
    meta, templates = data.meta, data.templates
    spec = parse_spec(base.description)
    question = questions_by_outcome(meta).get(int(base.id))
    question_spec = (
        parse_spec(question.get("description", "")) if question else {}
    )
    # Same merge as normalize_outcome: outcome keys win over question keys.
    values = {**question_spec, **spec}
    return OutcomeMarketDetail(
        **base.model_dump(),
        spec=spec,
        deployer=find_deployer(base.venue, meta),
        question_group=find_question_membership(int(base.id), meta, templates),
        settlement=settlement,
        rules=template_rules(base.name, values, templates),
    )

def normalize_market_detail(
    raw: dict[str, Any], data: MarketData
) -> OutcomeMarketDetail:
    """Build the rich detail model for one live outcome."""
    question = questions_by_outcome(data.meta).get(int(raw["outcome"]))
    return _build_detail(normalize_outcome(raw, data, question), data)

def normalize_settled_detail(
    settled: dict[str, Any], data: MarketData
) -> OutcomeMarketDetail:
    """Build the detail model for the settled outcome
    
    settledOutcome embeds the original outcome object as 'spec',
    so same normalizer applies. No live mids for settled markets, 
    both prices are None.
    """
    # A settled outcome's question may itself be gone from outcomeMeta;
    # then question members simply have no times or parent title, which
    # is acceptable.
    question = questions_by_outcome(data.meta).get(int(settled["spec"]["outcome"]))
    # replace() copies the frozen dataclass with some fields swapped:
    # settled markets have no live prices or trading context.
    settled_data = replace(data, mids={}, ctxs={}, tops={})
    base = normalize_outcome(settled["spec"], settled_data, question)
    base = base.model_copy(update={"status": "settled"})

    try:
        fraction: float | None = float(settled.get("settleFraction"))
    except (TypeError, ValueError):
        fraction = None

    winner: int | None = None
    if fraction == 1.0:
        winner = 0
    elif fraction == 0.0:
        winner = 1

    settlement = Settlement(
        settle_fraction=fraction,
        details=str(settled.get("details", "")),
        winning_side_index=winner,
    )
    return _build_detail(base, data, settlement)

def _parse_levels(raw_levels: Any) -> list[BookLevel]:
    """Convert raw {"px", "sz", "n"} dicts into BookLevels, skipping bad ones"""
    levels: list[BookLevel] = []
    for raw in raw_levels or []:
        try:
            levels.append(
                BookLevel(
                    price=float(raw["px"]),
                    size=float(raw["sz"]),
                    orders=int(raw["n"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            logger.warning("Skipping malformed book level: %r", raw)
    return levels

def normalize_order_book(raw: dict[str, Any], side_index: int) -> OrderBook:
    """Convert a raw l2Book response into domain's OrderBook model.

    Hyperliquid's `levels` is [bids, asks]. Both are sorted explicitly
    (best-first) rather than trusting upstream ordering.
    """
    levels = raw.get("levels") or [[], []]
    bids = sorted(_parse_levels(levels[0]), key=lambda lvl: lvl.price, reverse=True)
    asks = sorted(_parse_levels(levels[1]), key=lambda lvl: lvl.price)

    best_bid = bids[0].price if bids else None
    best_ask = asks[0].price if asks else None
    spread = (
        round(best_ask - best_bid, 6)
        if best_bid is not None and best_ask is not None
        else None
    )

    return OrderBook(
        coin=str(raw.get("coin", "")),
        side_index=side_index,
        fetched_at=datetime.fromtimestamp(
            int(raw.get("time", 0)) / 1000, tz=timezone.utc
        ),
        bids=bids,
        asks=asks,
        best_bid=best_bid,
        best_ask=best_ask,
        spread=spread,
    )


if __name__ == "__main__":
    # Standalone verification: full pipeline against live mainnet.
    import asyncio
    from collections import Counter

    import httpx

    from app.services.hyperliquid import HyperliquidClient

    async def main() -> None:
        async with httpx.AsyncClient() as http:
            client = HyperliquidClient(http)
            meta = await client.fetch_outcome_meta()
            mids = await client.fetch_all_mids()
            ctxs = index_outcome_ctxs(await client.fetch_spot_asset_ctxs())
            templates = index_templates(await client.fetch_outcome_templates())

        markets = normalize_markets(MarketData(meta, mids, ctxs, templates))
        raw_count = len(meta.get("outcomes", []))
        print(f"normalized {len(markets)} of {raw_count} outcomes\n")

        for m in markets[:3]:
            print(m.model_dump_json(by_alias=True, indent=2))

        fallbacks = [m for m in markets if m.question == m.description]
        no_event = [m for m in markets if m.event_at is None]
        no_time = [m for m in markets if m.resolves_by is None]
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
        print(f"no eventAt (deadline only or undated): {len(no_event)}")
        print(f"no resolvesBy (no time at all): {len(no_time)}")
        for m in no_time[:5]:
            print(f"  - {m.id} {m.name}: {m.description[:70]}")
        print(f"fully priced: {len(priced)}; price pairs summing to ~1: {pair_ok}")

        # The volume definition rests on two observed (undocumented)
        # facts: both sides report the same dayBaseVlm, and the two
        # sides' notional volumes add up to it. Check every market.
        with_ctx = 0
        mismatches: list[str] = []
        for m in markets:
            if len(m.sides) != 2:
                continue
            c0 = ctxs.get(m.sides[0].coin)
            c1 = ctxs.get(m.sides[1].coin)
            if c0 is None or c1 is None:
                continue
            with_ctx += 1
            base0 = float(c0["dayBaseVlm"])
            base1 = float(c1["dayBaseVlm"])
            notional = float(c0["dayNtlVlm"]) + float(c1["dayNtlVlm"])
            if abs(base0 - base1) > 1e-6 or abs(notional - base0) > 0.01 * max(base0, 1.0):
                mismatches.append(m.id)
        traded = [m for m in markets if (m.volume_24h or 0) > 0]
        print(f"\nmarkets with trading context: {with_ctx}; traded in 24h: {len(traded)}")
        print(f"volume invariant mismatches: {len(mismatches)} {mismatches[:5]}")
        print("top 5 by 24h volume:")
        for m in sorted(markets, key=lambda m: m.volume_24h or 0, reverse=True)[:5]:
            print(f"  {m.volume_24h or 0:>12,.0f}  {m.id:>6}  {m.question[:60]}")

        # Milestone 18.1: which markets got template wording, and one
        # sample title + side labels per raw name.
        questions = questions_by_outcome(meta)
        no_template: Counter[str] = Counter()
        no_rules: Counter[str] = Counter()
        samples: dict[str, OutcomeMarket] = {}
        markets_by_id = {m.id: m for m in markets}
        for raw in meta.get("outcomes", []):
            m = markets_by_id.get(str(raw.get("outcome")))
            if m is None:
                continue
            name = raw.get("name", "")
            question = questions.get(int(raw["outcome"]))
            question_spec = (
                parse_spec(question.get("description", "")) if question else {}
            )
            values = {**question_spec, **parse_spec(raw.get("description", ""))}
            if template_question(name, values, question, question_spec, templates) is None:
                no_template[name] += 1
            if template_rules(name, values, templates) is None:
                no_rules[name] += 1
            samples.setdefault(name, m)
        print(f"\ntemplates loaded: {len(templates)}")
        print(f"markets without template wording: {sum(no_template.values())}")
        for name, count in no_template.most_common():
            print(f"  {count:4d}  {name}")
        # Milestone 18.1b: rules need EVERY description placeholder filled.
        print(f"markets without own resolution rules: {sum(no_rules.values())}")
        for name, count in no_rules.most_common():
            print(f"  {count:4d}  {name}")
        print("one sample per market kind (title | side labels):")
        for name, m in samples.items():
            labels = " / ".join(side.label for side in m.sides)
            print(f"  [{name}]\n      {m.question[:110]}\n      sides: {labels}")

    asyncio.run(main())