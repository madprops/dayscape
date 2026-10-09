"""SQLite persistence with a full in-memory cache.

A journal produces at most ~365 rows a year, so the whole dataset is kept in a
dict after startup. Reads (views, search, stats) never touch disk; writes go
straight through to SQLite (WAL mode) so nothing is ever lost.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from collections.abc import Iterable, Iterator
from datetime import date, timedelta
from pathlib import Path

from dayscape.models import Entry

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    day         TEXT PRIMARY KEY,                       -- ISO date, YYYY-MM-DD
    score       INTEGER CHECK (score BETWEEN 1 AND 10), -- NULL = not rated
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._migrate()
        self._cache: dict[date, Entry] = {}
        self._load()

    # ------------------------------------------------------------------ setup
    def _migrate(self) -> None:
        (version,) = self._conn.execute("PRAGMA user_version").fetchone()
        if version < 1:
            self._conn.executescript(SCHEMA)
        self._conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        self._conn.commit()

    def _load(self) -> None:
        rows = self._conn.execute("SELECT day, score, notes FROM entries")
        self._cache = {
            date.fromisoformat(d): Entry(date.fromisoformat(d), s, n or "") for d, s, n in rows
        }

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------ reads
    def get(self, day: date) -> Entry | None:
        return self._cache.get(day)

    def __len__(self) -> int:
        return len(self._cache)

    def __iter__(self) -> Iterator[Entry]:
        return iter(sorted(self._cache.values(), key=lambda e: e.day))

    def all(self) -> list[Entry]:
        return list(self)

    def between(self, start: date, end: date) -> list[Entry]:
        """Entries with start <= day <= end, oldest first."""
        return sorted((e for d, e in self._cache.items() if start <= d <= end), key=lambda e: e.day)

    def years(self) -> list[int]:
        return sorted({d.year for d in self._cache})

    def first_day(self) -> date | None:
        return min(self._cache) if self._cache else None

    def streak(self, today: date | None = None) -> int:
        """Consecutive logged days ending today (or yesterday, if today is still blank)."""
        today = today or date.today()
        cursor = today if today in self._cache else today - timedelta(days=1)
        n = 0
        while cursor in self._cache:
            n += 1
            cursor -= timedelta(days=1)
        return n

    # ----------------------------------------------------------------- writes
    def save(self, day: date, score: int | None, notes: str) -> Entry | None:
        """Upsert a day. A day with no score and no text is deleted."""
        if score is not None and not 1 <= score <= 10:
            raise ValueError(f"score must be 1-10, got {score}")
        notes = notes.rstrip()
        if score is None and not notes.strip():
            self.delete(day)
            return None
        self._conn.execute(
            """
            INSERT INTO entries (day, score, notes) VALUES (?, ?, ?)
            ON CONFLICT(day) DO UPDATE SET
                score = excluded.score,
                notes = excluded.notes,
                updated_at = datetime('now')
            """,
            (day.isoformat(), score, notes),
        )
        self._conn.commit()
        entry = Entry(day, score, notes)
        self._cache[day] = entry
        return entry

    def delete(self, day: date) -> None:
        if day in self._cache:
            self._conn.execute("DELETE FROM entries WHERE day = ?", (day.isoformat(),))
            self._conn.commit()
            del self._cache[day]

    def bulk_save(self, entries: Iterable[Entry]) -> int:
        n = 0
        with self._conn:
            for e in entries:
                if e.is_empty:
                    continue
                self._conn.execute(
                    """
                    INSERT INTO entries (day, score, notes) VALUES (?, ?, ?)
                    ON CONFLICT(day) DO UPDATE SET
                        score = excluded.score, notes = excluded.notes,
                        updated_at = datetime('now')
                    """,
                    (e.day.isoformat(), e.score, e.notes.rstrip()),
                )
                self._cache[e.day] = Entry(e.day, e.score, e.notes.rstrip())
                n += 1
        return n

    # ----------------------------------------------------------- import/export
    def export_json(self, path: str | Path) -> int:
        data = {
            "app": "dayscape",
            "version": SCHEMA_VERSION,
            "entries": [
                {"date": e.day.isoformat(), "score": e.score, "notes": e.notes} for e in self
            ],
        }
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return len(data["entries"])

    def export_csv(self, path: str | Path) -> int:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["date", "weekday", "score", "notes"])
            for e in self:
                w.writerow([e.day.isoformat(), e.day.strftime("%A"), e.score or "", e.notes])
        return len(self)

    def import_json(self, path: str | Path) -> int:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        rows = data["entries"] if isinstance(data, dict) else data
        entries = []
        for r in rows:
            score = r.get("score")
            entries.append(
                Entry(
                    date.fromisoformat(r["date"]),
                    int(score) if score not in (None, "") else None,
                    r.get("notes") or "",
                )
            )
        return self.bulk_save(entries)
