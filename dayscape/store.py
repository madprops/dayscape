"""Qt-side wrapper around the database that broadcasts changes to every view."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QObject, Signal

from dayscape.db import Database
from dayscape.models import Entry


class Store(QObject):
    #: emitted with the changed ``date``, or ``None`` after bulk changes (import)
    changed = Signal(object)

    def __init__(self, db: Database, parent: QObject | None = None):
        super().__init__(parent)
        self.db = db

    def get(self, day: date) -> Entry | None:
        return self.db.get(day)

    def score(self, day: date) -> int | None:
        e = self.db.get(day)
        return e.score if e else None

    def all(self) -> list[Entry]:
        return self.db.all()

    def between(self, start: date, end: date) -> list[Entry]:
        return self.db.between(start, end)

    def save(self, day: date, score: int | None, notes: str) -> bool:
        """Persist a day; returns True if anything actually changed."""
        old = self.db.get(day)
        if old is None and score is None and not notes.strip():
            return False
        if old is not None and old.score == score and old.notes == notes.rstrip():
            return False
        self.db.save(day, score, notes)
        self.changed.emit(day)
        return True

    def import_json(self, path: str) -> int:
        n = self.db.import_json(path)
        self.changed.emit(None)
        return n
