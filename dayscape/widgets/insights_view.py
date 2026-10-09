"""Insights: the 'find trends' part — weekday patterns, trend lines, themes."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from dayscape import stats
from dayscape.models import SCORE_WORDS, WEEKDAYS, WEEKDAYS_SHORT
from dayscape.store import Store
from dayscape.theme import C
from dayscape.widgets.charts import DistributionChart, Row, RowList, TrendChart, WeekdayChart
from dayscape.widgets.common import Card, Segmented, StatTile, caps, label

RANGES = ["30 days", "90 days", "Year", "All time"]


class InsightsView(QWidget):
    daySelected = Signal(object)
    searchRequested = Signal(str)

    def __init__(self, store: Store, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self.year = date.today().year
        self.range_idx = 1

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 32)
        root.setSpacing(18)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(label("Insights", "h1"))
        self.subtitle = label("", "muted")
        titles.addWidget(self.subtitle)
        head.addLayout(titles)
        head.addStretch(1)
        self.range = Segmented(RANGES)
        self.range.set_index(self.range_idx)
        self.range.changed.connect(self._on_range)
        head.addWidget(self.range, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(head)

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t_avg = StatTile("Average vibe")
        self.t_logged = StatTile("Days logged")
        self.t_streak = StatTile("Current streak")
        self.t_calm = StatTile("Calmest day")
        self.t_wild = StatTile("Most unpredictable")
        for t in (self.t_avg, self.t_logged, self.t_streak, self.t_calm, self.t_wild):
            tiles.addWidget(t, 1)
        root.addLayout(tiles)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        wcard = Card(margins=20)
        wcard.body.addLayout(
            self._card_head("By weekday", "bar = average · whisker = how much it swings")
        )
        self.weekday = WeekdayChart()
        self.weekday.weekdayClicked.connect(self._search_weekday)
        wcard.body.addWidget(self.weekday)
        grid.addWidget(wcard, 0, 0, 1, 2)

        dcard = Card(margins=20)
        dcard.body.addLayout(self._card_head("Score spread", ""))
        self.dist = DistributionChart()
        self.dist.scoreClicked.connect(
            lambda s: self.searchRequested.emit(f"score:{s} {self._range_filter()}".strip())
        )
        dcard.body.addWidget(self.dist)
        grid.addWidget(dcard, 0, 2, 1, 1)

        tcard = Card(margins=20)
        self.trend_hint = label("", "statHint")
        th = QHBoxLayout()
        th.addWidget(caps("Vibe over time"))
        th.addStretch(1)
        th.addWidget(self.trend_hint)
        tcard.body.addLayout(th)
        self.trend = TrendChart()
        self.trend.daySelected.connect(self.daySelected)
        tcard.body.addWidget(self.trend)
        grid.addWidget(tcard, 1, 0, 1, 3)

        kcard = Card(margins=20)
        kcard.body.addLayout(self._card_head("Themes", "words & #tags vs. your average"))
        self.keywords = RowList("Write a few days of notes to see themes")
        self.keywords.rowClicked.connect(lambda w: self.searchRequested.emit(str(w)))
        kcard.body.addWidget(self.keywords)
        kcard.body.addStretch(1)
        grid.addWidget(kcard, 2, 0, 1, 2)

        pcard = Card(margins=20)
        pcard.body.addLayout(self._card_head("Peaks & dips", ""))
        self.peaks = RowList("No rated days in range")
        self.peaks.rowClicked.connect(self.daySelected)
        pcard.body.addWidget(self.peaks)
        pcard.body.addStretch(1)
        grid.addWidget(pcard, 2, 2, 1, 1)

        for c in range(3):
            grid.setColumnStretch(c, 1)
        root.addLayout(grid)
        root.addStretch(1)

        store.changed.connect(lambda _d: self.refresh() if self.isVisible() else None)
        self.refresh()

    @staticmethod
    def _card_head(title: str, hint: str) -> QHBoxLayout:
        h = QHBoxLayout()
        h.addWidget(caps(title))
        h.addStretch(1)
        if hint:
            h.addWidget(label(hint, "statHint"))
        return h

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def set_year(self, year: int) -> None:
        if year != self.year:
            self.year = year
            if self.range_idx == 2:
                self.refresh()

    def _on_range(self, idx: int) -> None:
        self.range_idx = idx
        self.refresh()

    def _bounds(self) -> tuple[date, date]:
        today = date.today()
        if self.range_idx == 0:
            return today - timedelta(days=29), today
        if self.range_idx == 1:
            return today - timedelta(days=89), today
        if self.range_idx == 2:
            return date(self.year, 1, 1), min(
                date(self.year, 12, 31), max(today, date(self.year, 1, 1))
            )
        first = self.store.db.first_day() or today - timedelta(days=29)
        return first, today

    def _range_filter(self) -> str:
        return f"year:{self.year}" if self.range_idx == 2 else ""

    def _search_weekday(self, wd: int) -> None:
        self.searchRequested.emit(
            f"day:{WEEKDAYS_SHORT[wd].lower()} {self._range_filter()}".strip()
        )

    def refresh(self) -> None:
        start, end = self._bounds()
        entries = self.store.between(start, end)
        rated = [e for e in entries if e.score is not None]
        span = (end - start).days + 1
        label_range = RANGES[self.range_idx] if self.range_idx != 2 else str(self.year)
        self.subtitle.setText(
            f"{start.day} {start.strftime('%b %Y')} – {end.day} {end.strftime('%b %Y')}"
        )

        s = stats.summarize(e.score for e in rated)
        if s.mean is not None:
            self.t_avg.set(f"{s.mean:.1f}", f"{SCORE_WORDS[round(s.mean)]} · {label_range}", s.mean)
        else:
            self.t_avg.set("–", "No ratings in range")
        self.t_logged.set(str(len(entries)), f"{round(100 * len(entries) / span)}% of {span} days")
        streak = self.store.db.streak()
        self.t_streak.set(
            f"{streak} day{'s' if streak != 1 else ''}",
            "keep it going" if streak else "log today to start one",
        )

        wd = stats.by_weekday(entries)
        valid = [(i, w) for i, w in enumerate(wd) if w.mean is not None and w.count >= 2]
        if valid:
            calm = min(valid, key=lambda x: x[1].std)
            wild = max(valid, key=lambda x: x[1].std)
            self.t_calm.set(
                WEEKDAYS[calm[0]],
                f"swings ±{calm[1].std:.1f} around {calm[1].mean:.1f}",
                calm[1].mean,
            )
            self.t_wild.set(
                WEEKDAYS[wild[0]],
                f"swings ±{wild[1].std:.1f} around {wild[1].mean:.1f}",
                wild[1].mean,
            )
        else:
            self.t_calm.set("–", "Needs more data")
            self.t_wild.set("–", "Needs more data")
        self.weekday.set_data(wd)
        self.dist.set_data(stats.distribution(entries))

        short_w, long_w = (3, 7) if span <= 31 else (7, 30) if span <= 400 else (14, 60)
        self.trend_hint.setText(
            f"<span style='color:{C.ACCENT_GLOW}'>━ {short_w}-day average</span>"
            f"&nbsp;&nbsp;&nbsp;<span style='color:{C.TEXT_DIM}'>┅ {long_w}-day average</span>"
        )
        all_entries = self.store.between(start - timedelta(days=long_w), end)
        self.trend.set_data(
            start,
            end,
            [(e.day, e.score) for e in rated],
            stats.rolling_mean(all_entries, short_w, start, end),
            stats.rolling_mean(all_entries, long_w, start, end),
        )

        kws = stats.keywords(entries, top=10)
        top_days = max((k.days for k in kws), default=1)
        self.keywords.set_rows(
            [
                Row(
                    ("#" + k.word[1:]) if k.is_tag else k.word,
                    k.word,
                    f"{k.days} days",
                    k.mean,
                    f"{'+' if k.delta >= 0 else '−'}{abs(k.delta):.1f}",
                    "#6CC67C" if k.delta > 0.3 else "#EA6A48" if k.delta < -0.3 else C.TEXT_FAINT,
                    k.days / top_days,
                )
                for k in kws
            ]
        )

        ordered = sorted(rated, key=lambda e: (e.score, e.day))
        picks = (
            list(reversed(ordered[-5:])) + ordered[:5]
            if len(ordered) >= 10
            else list(reversed(ordered))
        )
        self.peaks.set_rows(
            [
                Row(
                    e.day,
                    f"{WEEKDAYS_SHORT[e.day.weekday()]} {e.day.day} {e.day.strftime('%b')}",
                    e.lines[0] if e.lines else "",
                    e.score,
                )
                for e in picks
            ]
        )
