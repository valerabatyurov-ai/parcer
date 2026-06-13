from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from config import Settings
from schemas import Event
from services.normalizer import Normalizer
from utils.logging import logger


@dataclass(frozen=True, slots=True)
class EventPair:
    left: Event
    right: Event
    confidence: int
    normalized_home: str
    normalized_away: str
    normalized_league: str


@dataclass(frozen=True, slots=True)
class UnmatchedCandidate:
    left: Event
    right: Event
    confidence: int
    suggested_alias: str


class EventMatcher:
    def __init__(self, settings: Settings, normalizer: Normalizer) -> None:
        self.settings = settings
        self.normalizer = normalizer
        self.unmatched_candidates: list[UnmatchedCandidate] = []

    def match(self, events: list[Event]) -> list[EventPair]:
        self.unmatched_candidates = []
        pairs: list[EventPair] = []
        for index, left in enumerate(events):
            for right in events[index + 1 :]:
                if left.bookmaker == right.bookmaker:
                    continue
                result = self._match_pair(left, right)
                if result:
                    pairs.append(result)
        return pairs

    def _match_pair(self, left: Event, right: Event) -> EventPair | None:
        if left.sport != right.sport:
            return None

        time_diff = abs((self._aware(left.start_time) - self._aware(right.start_time)).total_seconds()) / 60
        if time_diff > self.settings.max_start_time_diff_minutes:
            return None

        direct = self._score_orientation(left, right, swapped=False)
        swapped = self._score_orientation(left, right, swapped=True)
        candidate = max([direct, swapped], key=lambda item: item["confidence"])

        if (
            candidate["team_score"] >= self.settings.team_match_threshold
            and candidate["league_score"] >= self.settings.league_match_threshold
        ):
            return EventPair(
                left=left,
                right=right,
                confidence=candidate["confidence"],
                normalized_home=candidate["home"],
                normalized_away=candidate["away"],
                normalized_league=candidate["league"],
            )

        if candidate["confidence"] >= 70:
            suggested_alias = (
                f"{candidate['home']} = {left.home_team}; "
                f"{candidate['away']} = {left.away_team}; "
                f"{candidate['league']} = {left.league}"
            )
            self.unmatched_candidates.append(
                UnmatchedCandidate(
                    left=left,
                    right=right,
                    confidence=int(candidate["confidence"]),
                    suggested_alias=suggested_alias,
                )
            )
            logger.bind(channel="unmatched").info(
                "Possible event match: {left_bookmaker}: {left_event}; {right_bookmaker}: {right_event}; "
                "sport={sport}; league={league}; confidence={confidence}%",
                left_bookmaker=left.bookmaker,
                left_event=left.event_name,
                right_bookmaker=right.bookmaker,
                right_event=right.event_name,
                sport=left.sport,
                league=left.league,
                confidence=candidate["confidence"],
            )
        return None

    def _score_orientation(self, left: Event, right: Event, swapped: bool) -> dict[str, int | str]:
        right_home = right.away_team if swapped else right.home_team
        right_away = right.home_team if swapped else right.away_team

        home = self.normalizer.score(left.home_team, right_home, "teams")
        away = self.normalizer.score(left.away_team, right_away, "teams")
        league = self.normalizer.score(left.league, right.league, "leagues")

        team_score = min(home.score, away.score)
        confidence = min(team_score, league.score)
        if team_score < self.settings.team_match_threshold or league.score < self.settings.league_match_threshold:
            confidence = min(confidence, team_score, league.score)

        return {
            "confidence": int(confidence),
            "team_score": int(team_score),
            "league_score": int(league.score),
            "home": home.normalized_left,
            "away": away.normalized_left,
            "league": league.normalized_left,
        }

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.astimezone()
        return value
