"""Suggested cross-venue matches for football questions (Milestone 22.2).

Suggestions are only candidates: a person reads both venues' rules and
confirms (or ignores) them. Scope, decision 3: Hyperliquid's three-way
football match questions ("Competition: Team A v Team B" with the
outcomes Team A / Draw / Team B), on Polymarket and Kalshi.

Matching uses WORD BOUNDARIES throughout: the 22 probe's substring
match found "nfl" inside "inflation".

22.2b: venues name clubs differently ("AEK Athens" on Hyperliquid and
Kalshi, plain "AEK" on Polymarket), so a team counts as present if ANY
of its distinctive words appears, and the search tries several queries
because Polymarket's relevance varies with the wording.
"""

import logging
import re
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Any

from app.models.market import OutcomeMarket
from app.models.venue import SuggestedPair, Suggestion
from app.services.kalshi import KalshiClient, kalshi_quote
from app.services.polymarket import PolymarketClient, polymarket_quote

logger = logging.getLogger(__name__)

# Letters that Unicode does not decompose into "base letter + accent",
# mapped by hand to their plain spelling (22.2c).
FOLD_TABLE = str.maketrans({
    "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ß": "ss",
    "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ı": "i",
})


def fold(text: str | None) -> str:
    """'Fenerbahçe' -> 'Fenerbahce', 'Bodø' -> 'Bodo' (22.2c).

    Hyperliquid writes "Fenerbahce", Polymarket "Fenerbahçe". NFKD
    normalization splits "ç" into "c" plus a combining cedilla, and the
    combining marks are then dropped; FOLD_TABLE covers letters that do
    not decompose. Applied to BOTH sides of every comparison.
    """
    decomposed = unicodedata.normalize("NFKD", (text or "").translate(FOLD_TABLE))
    return "".join(c for c in decomposed if not unicodedata.combining(c))

# Words too common in club names to identify a team ("FC Bayern Munich").
GENERIC_WORDS = {
    "fc", "fk", "afc", "cf", "ac", "sc", "as", "rc", "sk", "city", "united",
    "club", "the", "real", "de", "sporting",
}
# Words too common in competition names to identify a league.
GENERIC_COMPETITION_WORDS = {"league", "game", "cup", "the", "of", "matchday"}

KALSHI_SERIES_TTL_SECONDS = 24 * 3600  # decision 3: cache the list a day

# The same two teams meet more than once a season; a candidate event must
# be within this window of Hyperliquid's kickoff to be the same match.
SAME_MATCH_WINDOW = timedelta(days=1)


def has_word(text: str | None, word: str) -> bool:
    return re.search(rf"\b{re.escape(fold(word))}\b", fold(text), re.IGNORECASE) is not None


def team_words(team: str) -> list[str]:
    """A team's distinctive words, in name order: 'AEK Athens' ->
    ['AEK', 'Athens']; 'FC Shakhtar Donetsk' -> ['Shakhtar', 'Donetsk'].

    Three letters is enough ("AEK", "PSG"); generic club words are
    skipped. With no distinctive word at all ('Sporting CP'), the full
    name is used, which is more specific, not less.
    """
       # [^\W\d_]+ = runs of letters in ANY alphabet; [A-Za-z]+ would cut
    # "Fenerbahçe" into "Fenerbah" and "e". Folding first keeps it whole.
    words = [
        w for w in re.findall(r"[^\W\d_]+", fold(team))
        if w.lower() not in GENERIC_WORDS and len(w) >= 3
    ]
    return words or [team.strip()]


def team_present(text: str | None, team: str) -> bool:
    """True if ANY distinctive word of the team appears as a whole word.

    Deliberately loose (22.2b): a missed match is invisible, a wrong
    candidate is visible and a person rejects it. Every other check
    (both teams, open event, date window) still applies.
    """
    return any(has_word(text, word) for word in team_words(team))


def search_queries(home: str, away: str) -> list[str]:
    """Polymarket queries to try in order, without duplicates.

    In the 22.2b probe, "AEK Real Madrid" found the match while "Athens
    Madrid" and "AEK Athens Real Madrid" did not; no single wording can
    be trusted, so several are tried.
    """
    home_words, away_words = team_words(home), team_words(away)
    candidates = [
        f"{home_words[0]} {away_words[0]}",  # first distinctive words
        f"{home} {away}",  # full names
        f"{max(home_words, key=len)} {max(away_words, key=len)}",  # longest
    ]
    return list(dict.fromkeys(candidates))  # dedupe, keeping order


def near(value: Any, target: datetime | None) -> bool:
    """True if an ISO time is within SAME_MATCH_WINDOW of `target`.

    Missing or unparseable times pass: the person confirming sees the
    event anyway, and a missing field should not hide a real match.
    """
    if target is None or not value:
        return True
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return True
    return abs(when - target) <= SAME_MATCH_WINDOW


def parse_match_title(title: str) -> tuple[str, str, str] | None:
    """'UEFA Champions League Matchday 4: Shakhtar v Sporting CP'
    -> ('UEFA Champions League', 'Shakhtar', 'Sporting CP')."""
    competition, sep, teams = title.partition(":")
    if not sep or " v " not in teams:
        return None
    home, away = (t.strip() for t in teams.split(" v ", 1))
    competition = re.sub(r"\bMatchday\s+\d+\b", "", competition).strip()
    return competition, home, away


def competition_words(competition: str) -> set[str]:
    return {
        w.lower() for w in re.findall(r"[^\W\d_]+", fold(competition))
        if w.lower() not in GENERIC_COMPETITION_WORDS and len(w) >= 3
    }


class SuggestionFinder:
    def __init__(self, polymarket: PolymarketClient, kalshi: KalshiClient) -> None:
        self._polymarket = polymarket
        self._kalshi = kalshi
        self._series: list[dict[str, Any]] = []
        self._series_fetched_at = 0.0

    async def find(self, members: list[OutcomeMarket]) -> list[Suggestion]:
        """Candidates on each venue for one Hyperliquid football question.

        `members` are the question's outcomes (named + fallback). A venue
        that errors or finds nothing simply contributes no suggestion.
        """
        if not members or members[0].parent is None or members[0].parent.title is None:
            return []
        parsed = parse_match_title(members[0].parent.title)
        if parsed is None:
            return []
        competition, home, away = parsed

        suggestions = []
        for find_on_venue in (self._polymarket_suggestion, self._kalshi_suggestion):
            try:
                found = await find_on_venue(members, competition, home, away)
            except Exception:
                logger.exception("Suggestion lookup failed")
                found = None
            if found is not None:
                suggestions.append(found)
        return suggestions

    async def _polymarket_suggestion(
        self, members: list[OutcomeMarket], competition: str, home: str, away: str
    ) -> Suggestion | None:
        kickoff = members[0].event_at
        event = None
        for query in search_queries(home, away):
            events = await self._polymarket.search_events(query)
            event = next(
                (e for e in events
                 if team_present(e.get("title"), home)
                 and team_present(e.get("title"), away)
                 and not e.get("closed")
                 and near(e.get("endDate"), kickoff)),
                None,
            )
            if event is not None:
                break
        if event is None:
            return None
        markets = event.get("markets") or []

        def pick(member: OutcomeMarket) -> dict[str, Any] | None:
            label = member.parent.outcome_label if member.parent else ""
            if label == "Draw":
                return next((m for m in markets if has_word(m.get("question"), "draw")), None)
            return next(
                (m for m in markets
                 if team_present(m.get("question"), label)
                 and not has_word(m.get("question"), "draw")),
                None,
            )

        return self._build("polymarket", str(event.get("title", "")), members, pick, polymarket_quote)

    async def _kalshi_suggestion(
        self, members: list[OutcomeMarket], competition: str, home: str, away: str
    ) -> Suggestion | None:
        wanted = competition_words(competition)
        series = [
            s for s in await self._kalshi_series()
            if s.get("category") == "Sports"
            and has_word(s.get("title"), "game")
            and not has_word(s.get("title"), "women's")
            and len(wanted & competition_words(str(s.get("title", "")))) >= 2
        ]
        for one in series[:3]:
            for event in await self._kalshi.fetch_open_events(str(one.get("ticker"))):
                if not (team_present(event.get("title"), home) and team_present(event.get("title"), away)):
                    continue
                markets = event.get("markets") or []
                if markets and not near(markets[0].get("occurrence_datetime"), members[0].event_at):
                    continue

                def pick(member: OutcomeMarket) -> dict[str, Any] | None:
                    label = member.parent.outcome_label if member.parent else ""
                    if label == "Draw":
                        return next((m for m in markets if has_word(m.get("yes_sub_title"), "tie")), None)
                    return next((m for m in markets if team_present(m.get("yes_sub_title"), label)), None)

                return self._build("kalshi", str(event.get("title", "")), members, pick, kalshi_quote)
        return None

    async def _kalshi_series(self) -> list[dict[str, Any]]:
        if not self._series or time.monotonic() - self._series_fetched_at > KALSHI_SERIES_TTL_SECONDS:
            self._series = await self._kalshi.fetch_series()
            self._series_fetched_at = time.monotonic()
        return self._series

    @staticmethod
    def _build(venue, event_title, members, pick, to_quote) -> Suggestion | None:
        pairs: list[SuggestedPair] = []
        unmatched: list[str] = []
        for member in members:
            label = member.parent.outcome_label if member.parent else member.question
            raw = pick(member) if member.parent and member.parent.role == "named" else None
            if raw is None:
                unmatched.append(label)
            else:
                pairs.append(SuggestedPair(market_id=member.id, outcome_label=label, quote=to_quote(raw)))
        if not pairs:
            return None
        return Suggestion(
            venue=venue,
            event_title=event_title,
            pairs=pairs,
            unmatched=unmatched,
            rules=pairs[0].quote.rules,
        )