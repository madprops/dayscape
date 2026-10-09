"""Search query language.

Plain words match anywhere in a day's notes (case- and accent-insensitive,
all words must match). On top of that a few filters are understood:

    "exact phrase"        quoted phrase
    -word                 exclude days containing word
    #tag                  days tagged #tag (prefix match while typing)
    score:7  s:7          exact score          score:3-5    range
    score>=8  >=8  <4     comparisons          is:unrated   / is:rated
    day:mon  day:sat,sun  day:weekend  day:weekday
    year:2026  month:mar  month:3
"""

from __future__ import annotations

import operator
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from dayscape.models import TAG_RE, Entry

_TOKEN_RE = re.compile(r'(-?)"([^"]*)"?|(\S+)')
_SCORE_RE = re.compile(
    r"^(?:(?:score|s):?(?P<op1>>=|<=|>|<|=)?|(?P<op2>>=|<=|>|<|=))"
    r"(?P<a>\d{1,2})(?:(?:-|\.\.)(?P<b>\d{1,2}))?$"
)
_OPS: dict[str, Callable[[int, int], bool]] = {
    "=": operator.eq,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}
_DAY_ALIASES = {
    "mon": {0},
    "tue": {1},
    "wed": {2},
    "thu": {3},
    "fri": {4},
    "sat": {5},
    "sun": {6},
    "weekday": {0, 1, 2, 3, 4},
    "weekdays": {0, 1, 2, 3, 4},
    "weekend": {5, 6},
    "weekends": {5, 6},
}
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def fold(text: str) -> str:
    """Casefold and strip accents so 'cafe' finds 'Café'."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@dataclass
class Query:
    raw: str = ""
    terms: list[str] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    score_tests: list[Callable[[int], bool]] = field(default_factory=list)
    weekdays: set[int] = field(default_factory=set)
    years: set[int] = field(default_factory=set)
    months: set[int] = field(default_factory=set)
    rated: bool | None = None

    @property
    def is_empty(self) -> bool:
        return not (
            self.terms
            or self.excludes
            or self.tags
            or self.score_tests
            or self.weekdays
            or self.years
            or self.months
            or self.rated is not None
        )

    @property
    def highlights(self) -> list[str]:
        """Strings worth highlighting in results (folded)."""
        return [t for t in self.terms if t] + [f"#{t}" for t in self.tags]

    def matches(self, e: Entry) -> bool:
        if self.rated is True and e.score is None:
            return False
        if self.rated is False and e.score is not None:
            return False
        if self.score_tests and (e.score is None or not all(t(e.score) for t in self.score_tests)):
            return False
        if self.weekdays and e.day.weekday() not in self.weekdays:
            return False
        if self.years and e.day.year not in self.years:
            return False
        if self.months and e.day.month not in self.months:
            return False
        if self.terms or self.excludes:
            text = fold(e.notes)
            if not all(t in text for t in self.terms):
                return False
            if any(x in text for x in self.excludes):
                return False
        if self.tags:
            tags = {fold(t) for t in TAG_RE.findall(e.notes)}
            if not all(any(t.startswith(q) for t in tags) for q in self.tags):
                return False
        return True


def _parse_days(value: str) -> set[int]:
    out: set[int] = set()
    for part in value.split(","):
        key = part.strip()
        out |= _DAY_ALIASES.get(key) or _DAY_ALIASES.get(key[:3], set())
    return out


def _parse_months(value: str) -> set[int]:
    out: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= 12:
            out.add(int(part))
        elif part[:3] in _MONTHS:
            out.add(_MONTHS.index(part[:3]) + 1)
    return out


def parse(text: str) -> Query:
    q = Query(raw=text)
    for m in _TOKEN_RE.finditer(text):
        neg, phrase, word = m.group(1), m.group(2), m.group(3)
        if phrase is not None:
            (q.excludes if neg else q.terms).append(fold(phrase))
            continue
        tok = fold(word)

        sm = _SCORE_RE.match(tok)
        if sm:
            a = int(sm["a"])
            if sm["b"]:
                lo, hi = sorted((a, int(sm["b"])))
                q.score_tests.append(lambda s, lo=lo, hi=hi: lo <= s <= hi)
            else:
                op = _OPS[sm["op1"] or sm["op2"] or "="]
                q.score_tests.append(lambda s, op=op, a=a: op(s, a))
            continue

        key, sep, value = tok.partition(":")
        if sep and value:
            if key in ("day", "d"):
                q.weekdays |= _parse_days(value)
                continue
            if key in ("year", "y") and value.isdigit():
                q.years.add(int(value))
                continue
            if key in ("month", "m"):
                q.months |= _parse_months(value)
                continue
            if key == "is" and value in ("rated", "unrated"):
                q.rated = value == "rated"
                continue

        if tok.startswith("#") and len(tok) > 1:
            q.tags.append(tok[1:])
        elif tok.startswith("-") and len(tok) > 1:
            q.excludes.append(tok[1:])
        elif tok not in ("-", "#", '"'):
            q.terms.append(tok)
    return q


def search(entries: Iterable[Entry], query: Query | str, limit: int | None = None) -> list[Entry]:
    """Matching entries, newest first."""
    if isinstance(query, str):
        query = parse(query)
    hits = sorted((e for e in entries if query.matches(e)), key=lambda e: e.day, reverse=True)
    return hits[:limit] if limit else hits
