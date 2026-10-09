"""Plain data types shared by the storage, search and UI layers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

TAG_RE = re.compile(r"#([\w\-]+)", re.UNICODE)
BULLET_RE = re.compile(r"^\s*(?:[-*•·]\s*)")

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
WEEKDAYS_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
MONTHS_SHORT = tuple(m[:3] for m in MONTHS)

SCORE_WORDS = {
    1: "Awful",
    2: "Bad",
    3: "Rough",
    4: "Meh",
    5: "Okay",
    6: "Decent",
    7: "Good",
    8: "Great",
    9: "Excellent",
    10: "Perfect",
}


@dataclass(slots=True)
class Entry:
    day: date
    score: int | None = None
    notes: str = ""

    @property
    def is_empty(self) -> bool:
        return self.score is None and not self.notes.strip()

    @property
    def lines(self) -> list[str]:
        """Note lines with list markers stripped and blanks removed."""
        out = []
        for raw in self.notes.splitlines():
            text = BULLET_RE.sub("", raw).strip()
            if text:
                out.append(text)
        return out

    @property
    def tags(self) -> set[str]:
        return {t.casefold() for t in TAG_RE.findall(self.notes)}


def format_long(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def relative_label(d: date, today: date | None = None) -> str:
    today = today or date.today()
    delta = (today - d).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    if delta == -1:
        return "Tomorrow"
    if 1 < delta < 14:
        return f"{delta} days ago"
    if -14 < delta < -1:
        return f"In {-delta} days"
    if 14 <= delta < 60:
        return f"{delta // 7} weeks ago"
    if delta >= 60:
        months = delta // 30
        return f"{months} months ago" if months < 24 else f"{delta // 365} years ago"
    return "Upcoming"
