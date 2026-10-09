"""Pure-python statistics used by the views and the Insights dashboard."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import fmean, pstdev

from dayscape.models import BULLET_RE, TAG_RE, Entry


@dataclass(slots=True)
class Summary:
    count: int = 0  # rated days
    mean: float | None = None
    std: float | None = None
    low: int | None = None
    high: int | None = None


def summarize(scores: Iterable[int | None]) -> Summary:
    vals = [s for s in scores if s is not None]
    if not vals:
        return Summary()
    return Summary(len(vals), fmean(vals), pstdev(vals), min(vals), max(vals))


def mean_of(entries: Iterable[Entry]) -> float | None:
    return summarize(e.score for e in entries).mean


def by_weekday(entries: Iterable[Entry]) -> list[Summary]:
    buckets: dict[int, list[int]] = defaultdict(list)
    for e in entries:
        if e.score is not None:
            buckets[e.day.weekday()].append(e.score)
    return [summarize(buckets[i]) for i in range(7)]


def by_month(entries: Iterable[Entry], year: int) -> list[Summary]:
    buckets: dict[int, list[int]] = defaultdict(list)
    for e in entries:
        if e.day.year == year and e.score is not None:
            buckets[e.day.month].append(e.score)
    return [summarize(buckets[m]) for m in range(1, 13)]


def by_year(entries: Iterable[Entry]) -> dict[int, Summary]:
    buckets: dict[int, list[int]] = defaultdict(list)
    for e in entries:
        if e.score is not None:
            buckets[e.day.year].append(e.score)
    return {y: summarize(v) for y, v in sorted(buckets.items())}


def distribution(entries: Iterable[Entry]) -> list[int]:
    """Count of days per score, index 0 => score 1."""
    c = Counter(e.score for e in entries if e.score is not None)
    return [c.get(i, 0) for i in range(1, 11)]


def rolling_mean(
    entries: Sequence[Entry], window_days: int, start: date, end: date
) -> list[tuple[date, float]]:
    """Trailing calendar-window mean for every day that has a rated entry in its window."""
    scored = {e.day: e.score for e in entries if e.score is not None}
    out: list[tuple[date, float]] = []
    total = 0
    n = 0
    window_start = start - timedelta(days=window_days - 1)
    cursor = window_start
    while cursor <= end:
        if cursor in scored:
            total += scored[cursor]
            n += 1
        drop = cursor - timedelta(days=window_days)
        if drop in scored and drop >= window_start:
            total -= scored[drop]
            n -= 1
        if cursor >= start and n:
            out.append((cursor, total / n))
        cursor += timedelta(days=1)
    return out


# --------------------------------------------------------------- keywords
STOPWORDS = frozenset(
    [
        "a",
        "about",
        "after",
        "again",
        "all",
        "also",
        "am",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "doing",
        "done",
        "down",
        "for",
        "from",
        "get",
        "got",
        "had",
        "has",
        "have",
        "having",
        "he",
        "her",
        "here",
        "him",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "like",
        "me",
        "more",
        "most",
        "my",
        "no",
        "not",
        "now",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "our",
        "out",
        "over",
        "own",
        "really",
        "same",
        "she",
        "so",
        "some",
        "still",
        "such",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "up",
        "very",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "went",
        "go",
        "going",
        "day",
        "today",
        "bit",
        "lot",
        "kinda",
        "pretty",
        "much",
        "one",
        "two",
        "get",
        "gets",
        "getting",
    ]
)
_WORD_RE = re.compile(r"[^\W\d_][\w'\-]{2,}", re.UNICODE)


@dataclass(slots=True)
class Keyword:
    word: str
    days: int
    mean: float
    delta: float  # mean minus overall mean
    is_tag: bool


def keywords(entries: Sequence[Entry], top: int = 14, min_days: int = 2) -> list[Keyword]:
    """Most frequent tags/words and the average score of the days they appear on."""
    rated = [e for e in entries if e.score is not None]
    if not rated:
        return []
    overall = fmean(e.score for e in rated)
    days_by_word: dict[str, list[int]] = defaultdict(list)
    tags: set[str] = set()
    for e in rated:
        seen: set[str] = set()
        for t in TAG_RE.findall(e.notes):
            key = "#" + t.casefold()
            seen.add(key)
            tags.add(key)
        text = TAG_RE.sub(" ", "\n".join(BULLET_RE.sub("", ln) for ln in e.notes.splitlines()))
        for w in _WORD_RE.findall(text):
            w = w.casefold().strip("'-")
            if len(w) >= 3 and w not in STOPWORDS:
                seen.add(w)
        for w in seen:
            days_by_word[w].append(e.score)  # type: ignore[arg-type]

    out = [
        Keyword(w, len(v), fmean(v), fmean(v) - overall, w in tags)
        for w, v in days_by_word.items()
        if len(v) >= min_days
    ]
    out.sort(key=lambda k: (-k.days, -abs(k.delta), k.word))
    return out[:top]


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())
