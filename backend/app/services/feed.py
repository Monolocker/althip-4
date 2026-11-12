"""The unified feed (Milestone 24): news, sports, ticker and trending
items from different sources, normalized to one shape (FeedItem) and
interleaved round-robin, the structure bet.hypurr.fun uses.

Sources, all verified by the M24.0b / M24.1 probes:
  - news: Google News RSS search on the subjects of our busiest markets
    (one per category). GDELT refused every request (429), so it is not
    used.
  - sports: ESPN's JSON news endpoints for the NFL and NBA. ESPN's RSS
    feeds answered 202 with an empty body.
  - ticker: Hyperliquid metaAndAssetCtxs for the perps our price markets
    are about (default dex and HIP-3 dexes such as "xyz").
  - trending: our own snapshot, no external request.

Google News RSS and ESPN's JSON endpoints are not documented contracts:
they can change or refuse without notice. Fine for a local read-only
app; revisit before any deployment.
"""

import asyncio
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.models.feed import Feed, FeedItem, FeedKind, FeedSourceStatus
from app.models.market import OutcomeMarket
from app.services.hyperliquid import HyperliquidClient

logger = logging.getLogger(__name__)

# Decision 5 (M24.1): how long each source's items are reused.
NEWS_TTL_SECONDS = 300.0
SPORTS_TTL_SECONDS = 300.0
TICKER_TTL_SECONDS = 60.0  # two info requests of weight 20 per refresh
TRENDING_TTL_SECONDS = 0.0  # the market snapshot is already cached (15 s)

ITEMS_PER_KIND = 6
NEWS_QUERIES = 3  # one subject per category, busiest first
NEWS_PER_QUERY = 2

EXTERNAL_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
# An honest User-Agent: we never disguise the app as a browser.
USER_AGENT = "althip-4 (local read-only outcome market terminal)"
GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
ESPN_NEWS_URLS = {
    "NFL": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news",
    "NBA": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news",
}
# Trade page form seen in bet.hypurr.fun's feed: /trade/BTC, /trade/xyz:AAPL
HL_TRADE_URL = "https://app.hyperliquid.xyz/trade/"

# Crypto tickers as news writes them; unknown tickers get no news query.
ASSET_NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "HYPE": "Hyperliquid"}
# "NBA Regular Season: New Orleans Pelicans v Memphis Grizzlies"
SPORTS_TITLE = re.compile(r"^[^:]+:\s*(?P<home>.+?)\s+v\s+(?P<away>.+?)\s*$")
# "BTC touches ...", "Will ETH be above ...", "xyz:GOLD above ..."
UNDERLYING = re.compile(
    r"^(?:Will\s+)?(?P<asset>[A-Za-z0-9]+(?::[A-Za-z0-9]+)?)\s+(?:be\s+)?(?:touches|above|below)\b"
)

FetchItems = Callable[[], Awaitable[list[FeedItem]]]
MarketsSource = Callable[[], Awaitable[list[OutcomeMarket]]]


class FeedError(Exception):
    """A source could not be fetched or understood."""


# ---------------------------------------------------------------
# Market-derived helpers
# ---------------------------------------------------------------

def subject_title(market: OutcomeMarket) -> str:
    """The question a market is about: its parent question's title for
    an outcome of a multi-outcome question, otherwise its own."""
    if market.parent is not None and market.parent.title:
        return market.parent.title
    return market.question


def display_title(market: OutcomeMarket) -> str:
    """What a person reads: "Question: Outcome" for a question's outcome."""
    if market.parent is not None and market.parent.title:
        return f"{market.parent.title}: {market.parent.outcome_label}"
    return market.question


def news_query(title: str) -> str | None:
    """Search terms by market shape (M24.0b), instead of guessing words."""
    match = SPORTS_TITLE.match(title)
    if match:
        return f'"{match["home"]}" "{match["away"]}"'
    for symbol, name in ASSET_NAMES.items():
        if re.search(rf"\b{symbol}\b", title):
            return name
    if "Federal Open Market Committee" in title or "FOMC" in title:
        return "Federal Reserve rate decision"
    return None


def news_queries(markets: list[OutcomeMarket], limit: int) -> list[str]:
    """The busiest market's subject in each category, so one busy
    category cannot fill the whole news slot (decision 3b)."""
    ranked = sorted(markets, key=lambda m: m.volume_24h or 0, reverse=True)
    chosen: dict[str, str] = {}
    for market in ranked:
        category = market.category or ""
        if category in chosen:
            continue
        query = news_query(subject_title(market))
        if query is not None and query not in chosen.values():
            chosen[category] = query
            if len(chosen) == limit:
                break
    return list(chosen.values())


def underlyings(markets: list[OutcomeMarket]) -> list[str]:
    """Perps our price markets are about, most markets first (decision 4)."""
    counts = Counter(
        match["asset"]
        for market in markets
        if (match := UNDERLYING.match(subject_title(market))) is not None
    )
    return [asset for asset, _ in counts.most_common()]


def day_change(ctx: dict[str, Any]) -> float | None:
    try:
        mark = float(ctx.get("markPx") or 0)
        previous = float(ctx.get("prevDayPx") or 0)
    except (TypeError, ValueError):
        return None
    # prevDayPx 0 means "no history" (M20): no change, rather than -100%.
    return None if previous == 0 else (mark - previous) / previous


def _newest_first(items: list[FeedItem]) -> list[FeedItem]:
    # Items without a date go last instead of being guessed.
    return sorted(
        items,
        key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


# ---------------------------------------------------------------
# Source adapters: raw response -> list[FeedItem]
# ---------------------------------------------------------------

async def _get(http: httpx.AsyncClient, url: str, params: dict[str, str] | None = None) -> bytes:
    try:
        response = await http.get(
            url, params=params, headers={"User-Agent": USER_AGENT}, timeout=EXTERNAL_TIMEOUT
        )
    except httpx.HTTPError as exc:
        raise FeedError(f"{type(exc).__name__} for {url}") from exc
    # 202 with an empty body is how ESPN's RSS refused us: treat any
    # non-200 as a failure rather than as "no news".
    if response.status_code != 200:
        raise FeedError(f"HTTP {response.status_code} for {url}")
    return response.content


def parse_google_news(body: bytes) -> list[FeedItem]:
    """Google News RSS: <item><title>Headline - Outlet</title><link>,
    <pubDate>, <source url="...">Outlet</source>. Links go through
    news.google.com, which forwards the reader to the outlet."""
    try:
        root = ET.fromstring(body)  # expat 2.7.4 (M24.0): entity attacks refused
    except ET.ParseError as exc:
        raise FeedError(f"Google News returned invalid XML: {exc}") from exc
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        source = (item.findtext("source") or "").strip() or None
        if source is not None:
            title = title.removesuffix(f" - {source}")
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError):
            published = None
        items.append(
            FeedItem(kind="news", text=title, url=link, source=source, published_at=published)
        )
    return items


def parse_espn_news(body: bytes) -> list[FeedItem]:
    """ESPN JSON: {"articles": [{"headline", "published", "links":
    {"web": {"href"}}}]} (shape seen in the M24.1 probe)."""
    try:
        articles = json.loads(body).get("articles", [])
    except (ValueError, AttributeError) as exc:
        raise FeedError(f"ESPN returned unexpected JSON: {exc}") from exc
    items = []
    for article in articles:
        headline = str(article.get("headline") or "").strip()
        link = ((article.get("links") or {}).get("web") or {}).get("href")
        if not headline or not link:
            continue
        try:
            published = datetime.fromisoformat(str(article.get("published")))
        except ValueError:
            published = None
        items.append(
            FeedItem(kind="sports", text=headline, url=link, source="ESPN", published_at=published)
        )
    return items


def ticker_item(asset: str, ctx: dict[str, Any]) -> FeedItem:
    return FeedItem(
        kind="ticker",
        # "xyz:GOLD" reads as "GOLD"; the link keeps the full name.
        text=asset.split(":", 1)[-1],
        url=f"{HL_TRADE_URL}{asset}",
        source="Hyperliquid",
        change_24h=day_change(ctx),
    )


def trending_items(markets: list[OutcomeMarket], limit: int) -> list[FeedItem]:
    """Our busiest binary markets with a price. Only binary payouts have
    prices that are probabilities (M18), so scalar markets are skipped."""
    ranked = sorted(markets, key=lambda m: m.volume_24h or 0, reverse=True)
    items = []
    for market in ranked:
        price = market.sides[0].price if market.sides else None
        if market.payout != "binary" or price is None:
            continue
        items.append(
            FeedItem(
                kind="trending",
                text=display_title(market),
                market_id=market.id,
                probability=price,
            )
        )
        if len(items) == limit:
            break
    return items


def interleave(lists: list[list[FeedItem]]) -> list[FeedItem]:
    """Round-robin: the first of each list, then the second of each, ...
    A short list simply runs out; the others carry on."""
    merged = []
    for index in range(max((len(items) for items in lists), default=0)):
        for items in lists:
            if index < len(items):
                merged.append(items[index])
    return merged


# ---------------------------------------------------------------
# Caching, failure isolation, and the feed itself
# ---------------------------------------------------------------

class CachedSource:
    """One source with its own refresh interval.

    A failed refresh keeps the last good items (a stale headline beats
    an empty strip) and is not retried before the interval is over, so
    a source that is down is not hammered. The lock makes concurrent
    requests share one refresh instead of each starting their own.
    """

    def __init__(self, kind: FeedKind, ttl_seconds: float, fetch: FetchItems) -> None:
        self.kind = kind
        self._ttl = ttl_seconds
        self._fetch = fetch
        self._lock = asyncio.Lock()
        self._items: list[FeedItem] = []
        self._fetched_at: datetime | None = None
        self._attempted_at: float | None = None  # monotonic
        self._error: str | None = None

    async def get(self) -> tuple[list[FeedItem], FeedSourceStatus]:
        async with self._lock:
            due = (
                self._attempted_at is None
                or time.monotonic() - self._attempted_at >= self._ttl
            )
            if due:
                self._attempted_at = time.monotonic()
                try:
                    self._items = await self._fetch()
                    self._fetched_at = datetime.now(timezone.utc)
                    self._error = None
                except Exception as exc:
                    # Any failure, whatever its type, stays inside this
                    # source: the other kinds are still served.
                    logger.warning("Feed source %s failed: %s", self.kind, exc)
                    self._error = f"{type(exc).__name__}: {exc}"
            status = FeedSourceStatus(
                kind=self.kind,
                ok=self._error is None,
                items=len(self._items),
                fetched_at=self._fetched_at,
                error=self._error,
            )
            return list(self._items), status


class FeedService:
    def __init__(
        self,
        http: httpx.AsyncClient,
        hyperliquid: HyperliquidClient,
        markets_source: MarketsSource,
    ) -> None:
        self._http = http
        self._hyperliquid = hyperliquid
        self._markets = markets_source
        # Order here is the interleaving order (news, sports, ticker, trending).
        self._sources = [
            CachedSource("news", NEWS_TTL_SECONDS, self._news),
            CachedSource("sports", SPORTS_TTL_SECONDS, self._sports),
            CachedSource("ticker", TICKER_TTL_SECONDS, self._ticker),
            CachedSource("trending", TRENDING_TTL_SECONDS, self._trending),
        ]

    async def feed(self) -> Feed:
        # Sources refresh concurrently: the slowest one sets the wait,
        # not the sum of all four.
        results = await asyncio.gather(*(source.get() for source in self._sources))
        return Feed(
            generated_at=datetime.now(timezone.utc),
            items=interleave([items[:ITEMS_PER_KIND] for items, _ in results]),
            sources=[status for _, status in results],
        )

    async def _news(self) -> list[FeedItem]:
        queries = news_queries(await self._markets(), NEWS_QUERIES)
        if not queries:
            return []
        bodies = await asyncio.gather(
            *(
                _get(
                    self._http,
                    GOOGLE_NEWS_URL,
                    {"q": f"{query} when:2d", "hl": "en-US", "gl": "US", "ceid": "US:en"},
                )
                for query in queries
            ),
            return_exceptions=True,
        )
        items: list[FeedItem] = []
        seen: set[str] = set()
        errors = []
        for query, body in zip(queries, bodies):
            try:
                if isinstance(body, BaseException):
                    raise body
                parsed = parse_google_news(body)
            except Exception as exc:
                # One query failing (or malformed) must not cost the others.
                logger.warning("News query %r failed: %s", query, exc)
                errors.append(f"{query}: {exc}")
                continue
            for item in _newest_first(parsed)[:NEWS_PER_QUERY]:
                if item.text not in seen:
                    seen.add(item.text)
                    items.append(item)
        if not items and errors:
            raise FeedError("; ".join(errors))
        return items

    async def _sports(self) -> list[FeedItem]:
        bodies = await asyncio.gather(
            *(_get(self._http, url) for url in ESPN_NEWS_URLS.values()),
            return_exceptions=True,
        )
        items: list[FeedItem] = []
        seen: set[str] = set()
        errors = []
        for league, body in zip(ESPN_NEWS_URLS, bodies):
            try:
                if isinstance(body, BaseException):
                    raise body
                parsed = parse_espn_news(body)
            except Exception as exc:
                logger.warning("ESPN %s news failed: %s", league, exc)
                errors.append(f"{league}: {exc}")
                continue
            # A story can appear in more than one league's list.
            for item in parsed:
                if item.url not in seen:
                    seen.add(item.url or "")
                    items.append(item)
        if not items and errors:
            raise FeedError("; ".join(errors))
        return _newest_first(items)

    async def _ticker(self) -> list[FeedItem]:
        assets = underlyings(await self._markets())[:ITEMS_PER_KIND]
        # One request per perp dex actually needed: "" for BTC, "xyz" for xyz:GOLD.
        dexes = sorted({asset.split(":", 1)[0] if ":" in asset else "" for asset in assets})
        contexts: dict[str, dict[str, Any]] = {}
        for dex in dexes:
            meta, ctxs = await self._hyperliquid.fetch_perp_asset_ctxs(dex)
            names = [str(asset.get("name")) for asset in meta.get("universe", [])]
            contexts.update(zip(names, ctxs))
        return [ticker_item(asset, contexts[asset]) for asset in assets if asset in contexts]

    async def _trending(self) -> list[FeedItem]:
        return trending_items(await self._markets(), ITEMS_PER_KIND)