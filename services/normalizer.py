from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - fallback for minimal local installs
    from difflib import SequenceMatcher

    class fuzz:  # type: ignore[no-redef]
        @staticmethod
        def ratio(a: str, b: str) -> int:
            return int(SequenceMatcher(None, a, b).ratio() * 100)


from config import DATA_DIR


TECHNICAL_PATTERNS = [
    r"\([^)]*\)",
    r"\[[^]]*\]",
    r"\bfc\b",
    r"\bфк\b",
]


@dataclass(frozen=True, slots=True)
class MatchScore:
    matched: bool
    score: int
    normalized_left: str
    normalized_right: str


class Normalizer:
    def __init__(self, aliases_path: Path | None = None) -> None:
        self.aliases_path = aliases_path or DATA_DIR / "aliases.yaml"
        self.aliases = self._load_aliases(self.aliases_path)
        self.alias_lookup = {
            group: self._build_lookup(values)
            for group, values in self.aliases.items()
            if isinstance(values, dict)
        }

    def normalize_team(self, value: str) -> str:
        return self.apply_alias("teams", self.clean_text(value))

    def normalize_league(self, value: str) -> str:
        return self.apply_alias("leagues", self.clean_text(value))

    def normalize_market(self, value: str) -> str:
        return self.apply_alias("markets", self.clean_text(value))

    def clean_text(self, value: str) -> str:
        text = value.lower().replace("ё", "е")
        text = text.replace("–", "-").replace("—", "-")
        for pattern in TECHNICAL_PATTERNS:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
        text = re.sub(r"[.,'`\"|/\\]+", " ", text)
        text = re.sub(r"[^0-9a-zа-я+\-\s]", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def apply_alias(self, group: str, cleaned_value: str) -> str:
        return self.alias_lookup.get(group, {}).get(cleaned_value, cleaned_value)

    def score(self, left: str, right: str, group: str = "teams") -> MatchScore:
        left_normalized = self.apply_alias(group, self.clean_text(left))
        right_normalized = self.apply_alias(group, self.clean_text(right))
        if left_normalized == right_normalized:
            return MatchScore(True, 100, left_normalized, right_normalized)
        value = fuzz.ratio(left_normalized, right_normalized)
        return MatchScore(False, int(value), left_normalized, right_normalized)

    def _load_aliases(self, path: Path) -> dict:
        if not path.exists():
            return {"teams": {}, "leagues": {}, "markets": {}}
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {"teams": {}, "leagues": {}, "markets": {}}

    def _build_lookup(self, values: dict) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for canonical, aliases in values.items():
            canonical_clean = self.clean_text(str(canonical))
            lookup[canonical_clean] = canonical_clean
            for alias in aliases or []:
                lookup[self.clean_text(str(alias))] = canonical_clean
        return lookup
