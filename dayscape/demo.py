"""Deterministic sample data so the app can be explored before real use (`--demo`)."""

from __future__ import annotations

import math
import random
from datetime import date, timedelta

from dayscape.models import Entry

_WEEKDAY_BIAS = [-1.3, -0.4, 0.0, 0.2, 0.9, 1.4, 0.5]  # Mon .. Sun

_GOOD = [
    "long walk by the river",
    "cooked something new",
    "great chat with Sam",
    "finished the feature",
    "gym — new PR #gym",
    "slept 8h #sleep",
    "sunny all day",
    "band practice #music",
    "read for an hour",
    "pizza night with friends",
    "bike ride #outdoors",
    "productive deep work",
    "climbing session #gym",
    "called mom",
    "found a cool café",
    "movie night",
    "shipped release #work",
    "hiking #outdoors",
    "lazy morning, coffee in bed",
]
_BAD = [
    "slept badly #sleep",
    "too many meetings #work",
    "headache",
    "rain all day",
    "deadline stress #work",
    "argument at home",
    "skipped gym",
    "doomscrolling",
    "car trouble",
    "felt tired",
    "bug hunt that went nowhere #work",
    "missed the bus",
    "overslept, rushed everything",
    "noisy neighbours",
]
_NEUTRAL = [
    "groceries",
    "laundry",
    "standup + emails #work",
    "cleaned the flat",
    "paid bills",
    "meal prep",
    "dentist",
    "watched some youtube",
    "worked from home #work",
    "errands",
]


def generate(days: int = 430, end: date | None = None, seed: int = 7) -> list[Entry]:
    rng = random.Random(seed)
    end = end or date.today()
    start = end - timedelta(days=days - 1)
    out: list[Entry] = []
    for i in range(days):
        d = start + timedelta(days=i)
        if rng.random() < 0.08:  # occasionally forget to log
            continue
        season = 0.8 * math.sin((d.timetuple().tm_yday / 365.0) * 2 * math.pi - 1.2)
        drift = 0.6 * math.sin(i / 47.0)
        raw = 6.2 + _WEEKDAY_BIAS[d.weekday()] + season + drift + rng.gauss(0, 1.35)
        score = max(1, min(10, round(raw)))

        n = rng.choice([2, 3, 3, 3, 4, 4, 5])
        pool_weights = (0.65, 0.1) if score >= 8 else (0.15, 0.6) if score <= 4 else (0.35, 0.25)
        lines: list[str] = []
        for _ in range(n):
            r = rng.random()
            src = _GOOD if r < pool_weights[0] else _BAD if r < sum(pool_weights) else _NEUTRAL
            line = rng.choice(src)
            if line not in lines:
                lines.append(line)
        notes = "\n".join(f"- {ln}" for ln in lines)
        if rng.random() < 0.03:
            notes = ""
        out.append(Entry(d, score if rng.random() > 0.02 else None, notes))
    return out
