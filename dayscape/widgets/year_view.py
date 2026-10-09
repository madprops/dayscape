"""Year at a glance: day heatmap, week averages, weekday averages, month & year strips."""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QToolTip, QVBoxLayout, QWidget

from dayscape import stats
from dayscape.models import MONTHS, MONTHS_SHORT, SCORE_WORDS, WEEKDAYS, WEEKDAYS_SHORT
from dayscape.store import Store
from dayscape.theme import C, font, mix, score_color, text_on, tint
from dayscape.widgets.common import (
    Card,
    Legend,
    StatTile,
    caps,
    fill_round,
    icon_button,
    label,
    score_pill,
    stroke_round,
)


def tooltip_html(d: date, score: int | None, lines: list[str]) -> str:
    head = f"<b>{WEEKDAYS[d.weekday()]}</b>, {d.day} {MONTHS[d.month - 1]} {d.year}"
    if score:
        c = score_color(score).name()
        head += f"&nbsp;&nbsp;<b style='color:{c}'>{score} · {SCORE_WORDS[score]}</b>"
    body = "".join(f"<br><span style='color:{C.TEXT_DIM}'>• {ln}</span>" for ln in lines[:6])
    if not score and not lines:
        body = f"<br><span style='color:{C.TEXT_FAINT}'>Nothing logged</span>"
    return f"<div style='white-space:pre'>{head}{body}</div>"


class YearHeatmap(QWidget):
    daySelected = Signal(object)
    weekClicked = Signal(object)  # monday date
    weekdayClicked = Signal(int)

    LEFT = 40
    TOP = 26
    RIGHT = 64
    MAX_STEP = 30.0

    def __init__(self, store: Store, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self.year = date.today().year
        self.selected: date | None = None
        self._hover: tuple[str, object] | None = None
        self.setMouseTracking(True)
        self.setMinimumWidth(600)

    # geometry ---------------------------------------------------------------
    @property
    def first_monday(self) -> date:
        jan1 = date(self.year, 1, 1)
        return jan1 - timedelta(days=jan1.weekday())

    @property
    def cols(self) -> int:
        return (date(self.year, 12, 31) - self.first_monday).days // 7 + 1

    def step(self) -> float:
        avail = self.width() - self.LEFT - self.RIGHT
        return min(self.MAX_STEP, avail / self.cols)

    def grid_width(self) -> float:
        return self.step() * self.cols

    def week_row_y(self) -> float:
        return self.TOP + 7 * self.step() + 12

    def needed_height(self) -> int:
        s = self.step()
        return int(self.week_row_y() + s * 0.62 + 4)

    def resizeEvent(self, e):
        h = self.needed_height()
        if self.height() != h:
            self.setFixedHeight(h)
        super().resizeEvent(e)

    def cell_rect(self, d: date) -> QRectF:
        s = self.step()
        gap = max(2.0, s * 0.14)
        idx = (d - self.first_monday).days
        col, row = divmod(idx, 7)
        return QRectF(self.LEFT + col * s, self.TOP + row * s, s - gap, s - gap)

    def set_year(self, year: int) -> None:
        self.year = year
        self.setFixedHeight(self.needed_height())
        self.update()

    def set_selected(self, d: date) -> None:
        self.selected = d
        self.update()

    # data -----------------------------------------------------------------
    def _week_mean(self, col: int) -> tuple[float | None, int]:
        start = self.first_monday + timedelta(weeks=col)
        days = [start + timedelta(days=i) for i in range(7)]
        scores = [self.store.score(d) for d in days if d.year == self.year]
        s = stats.summarize(scores)
        return s.mean, s.count

    # painting -------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.step()
        gap = max(2.0, s * 0.14)
        radius = max(2.5, s * 0.22)
        today = date.today()

        # month labels
        p.setFont(font(11, QFont.Weight.DemiBold))
        for m in range(1, 13):
            first = date(self.year, m, 1)
            col = (first - self.first_monday).days // 7
            p.setPen(
                QColor(
                    C.TEXT_DIM
                    if first.month == today.month and self.year == today.year
                    else C.TEXT_FAINT
                )
            )
            p.drawText(QPointF(self.LEFT + col * s + 1, self.TOP - 10), MONTHS_SHORT[m - 1])

        # weekday labels
        p.setFont(font(11))
        p.setPen(QColor(C.TEXT_FAINT))
        for r in range(7):
            rect = QRectF(0, self.TOP + r * s, self.LEFT - 10, s - gap)
            p.drawText(
                rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, WEEKDAYS_SHORT[r]
            )

        # day cells
        d = date(self.year, 1, 1)
        end = date(self.year, 12, 31)
        while d <= end:
            rect = self.cell_rect(d)
            e = self.store.get(d)
            if e and e.score:
                fill_round(p, rect, radius, score_color(e.score))
            else:
                fill_round(p, rect, radius, C.EMPTY if d <= today else C.SURFACE)
                if e and e.notes.strip():
                    p.setBrush(QColor(C.TEXT_FAINT))
                    p.drawEllipse(rect.center(), s * 0.09, s * 0.09)
            if d == today:
                stroke_round(p, rect, radius, C.TEXT, 1.6)
            d += timedelta(days=1)

        # hover + selection
        if self._hover and self._hover[0] == "day":
            stroke_round(p, self.cell_rect(self._hover[1]), radius, mix(C.TEXT, C.BG, 0.35), 1.4)
        if self.selected and self.selected.year == self.year:
            r = self.cell_rect(self.selected).adjusted(-2.5, -2.5, 2.5, 2.5)
            stroke_round(p, r, radius + 2, C.ACCENT, 2.2)

        # week average row
        wy = self.week_row_y()
        p.setFont(font(10, QFont.Weight.DemiBold))
        p.setPen(QColor(C.TEXT_FAINT))
        p.drawText(
            QRectF(0, wy, self.LEFT - 10, s * 0.5),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            "Week",
        )
        for col in range(self.cols):
            mean, _n = self._week_mean(col)
            rect = QRectF(self.LEFT + col * s, wy, s - gap, s * 0.5)
            fill_round(p, rect, rect.height() / 2.4, score_color(mean) if mean else C.SURFACE)
            if self._hover and self._hover == ("week", col):
                stroke_round(
                    p, rect.adjusted(-1.5, -1.5, 1.5, 1.5), rect.height() / 2, C.TEXT_DIM, 1.2
                )

        # weekday averages column
        x0 = self.LEFT + self.grid_width() + 12
        p.setFont(font(10, QFont.Weight.DemiBold))
        p.setPen(QColor(C.TEXT_FAINT))
        p.drawText(
            QRectF(x0, self.TOP - 22, self.RIGHT - 14, 14), Qt.AlignmentFlag.AlignCenter, "AVG"
        )
        year_entries = self.store.between(date(self.year, 1, 1), end)
        wd = stats.by_weekday(year_entries)
        for r in range(7):
            h = min(s - gap, 22)
            rect = QRectF(x0, self.TOP + r * s + (s - gap - h) / 2, self.RIGHT - 14, h)
            score_pill(p, rect, wd[r].mean)
            if self._hover and self._hover == ("weekday", r):
                stroke_round(p, rect.adjusted(-2, -2, 2, 2), rect.height() / 2 + 2, C.TEXT_DIM, 1.2)
        p.end()

    # interaction ------------------------------------------------------------
    def _hit(self, pos: QPointF) -> tuple[str, object] | None:
        s = self.step()
        x, y = pos.x() - self.LEFT, pos.y()
        if 0 <= x < self.grid_width():
            col = int(x // s)
            if self.TOP <= y < self.TOP + 7 * s:
                row = int((y - self.TOP) // s)
                d = self.first_monday + timedelta(days=col * 7 + row)
                if d.year == self.year:
                    return ("day", d)
            wy = self.week_row_y()
            if wy - 2 <= y <= wy + s * 0.5 + 2:
                return ("week", col)
        x0 = self.LEFT + self.grid_width() + 12
        if x0 <= pos.x() <= x0 + self.RIGHT - 14 and self.TOP <= y < self.TOP + 7 * s:
            return ("weekday", int((y - self.TOP) // s))
        return None

    def mouseMoveEvent(self, e):
        hit = self._hit(e.position())
        if hit != self._hover:
            self._hover = hit
            self.update()
            self.setCursor(Qt.CursorShape.PointingHandCursor if hit else Qt.CursorShape.ArrowCursor)
        if not hit:
            QToolTip.hideText()
            return
        kind, val = hit
        gp = e.globalPosition().toPoint()
        if kind == "day":
            ent = self.store.get(val)
            QToolTip.showText(
                gp, tooltip_html(val, ent.score if ent else None, ent.lines if ent else []), self
            )
        elif kind == "week":
            mean, n = self._week_mean(val)
            start = self.first_monday + timedelta(weeks=val)
            iso = start.isocalendar()[1]
            txt = f"<b>Week {iso}</b> · {start.day} {MONTHS_SHORT[start.month - 1]}"
            txt += (
                f"<br>avg <b>{mean:.1f}</b> over {n} day{'s' if n != 1 else ''}"
                if mean
                else "<br>No ratings"
            )
            QToolTip.showText(gp, txt, self)
        else:
            QToolTip.showText(
                gp, f"Average <b>{WEEKDAYS[val]}</b> in {self.year}<br>Click to list them", self
            )

    def leaveEvent(self, _):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        hit = self._hit(e.position())
        if not hit or e.button() != Qt.MouseButton.LeftButton:
            return
        kind, val = hit
        if kind == "day":
            self.daySelected.emit(val)
        elif kind == "week":
            self.weekClicked.emit(self.first_monday + timedelta(weeks=val))
        else:
            self.weekdayClicked.emit(val)


@dataclass
class StripItem:
    key: object
    title: str
    mean: float | None
    subtitle: str
    spark: list[float | None] = field(default_factory=list)
    highlight: bool = False


class SummaryStrip(QWidget):
    """A row of tinted tiles (months or years) with a mini sparkline each."""

    itemClicked = Signal(object)

    def __init__(self, height: int = 112, parent: QWidget | None = None):
        super().__init__(parent)
        self.items: list[StripItem] = []
        self._hover: int | None = None
        self.setFixedHeight(height)
        self.setMouseTracking(True)

    def set_items(self, items: list[StripItem]) -> None:
        self.items = items
        self.update()

    def _rect(self, i: int) -> QRectF:
        n = max(1, len(self.items))
        gap = 8
        w = (self.width() - gap * (n - 1)) / n
        return QRectF(i * (w + gap), 0, w, self.height())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i, it in enumerate(self.items):
            r = self._rect(i)
            fill_round(p, r, 12, tint(it.mean, 0.20 if self._hover != i else 0.30))
            if it.highlight:
                stroke_round(p, r, 12, C.ACCENT, 1.6)
            elif self._hover == i:
                stroke_round(p, r, 12, C.BORDER_STRONG, 1.0)
            inner = r.adjusted(12, 10, -12, -10)
            p.setFont(font(11, QFont.Weight.DemiBold))
            p.setPen(QColor(C.TEXT_DIM))
            p.drawText(inner, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, it.title)
            p.setFont(font(22 if r.width() > 70 else 18, QFont.Weight.Bold))
            p.setPen(score_color(it.mean) if it.mean else QColor(C.TEXT_FAINT))
            p.drawText(
                QRectF(inner.left(), inner.top() + 16, inner.width(), 30),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{it.mean:.1f}" if it.mean else "–",
            )
            p.setFont(font(10))
            p.setPen(QColor(C.TEXT_FAINT))
            p.drawText(
                QRectF(inner.left(), inner.top() + 46, inner.width(), 14),
                Qt.AlignmentFlag.AlignLeft,
                it.subtitle,
            )
            # sparkline bars
            if it.spark:
                base = inner.bottom()
                hmax = 20.0
                n = len(it.spark)
                bw = inner.width() / n
                for k, v in enumerate(it.spark):
                    if v is None:
                        continue
                    h = max(2.0, hmax * v / 10)
                    br = QRectF(inner.left() + k * bw, base - h, max(1.0, bw - 1), h)
                    p.fillRect(br, score_color(v))
        p.end()

    def _hit(self, pos: QPointF) -> int | None:
        for i in range(len(self.items)):
            if self._rect(i).contains(pos):
                return i
        return None

    def mouseMoveEvent(self, e):
        h = self._hit(e.position())
        if h != self._hover:
            self._hover = h
            self.setCursor(
                Qt.CursorShape.PointingHandCursor if h is not None else Qt.CursorShape.ArrowCursor
            )
            self.update()

    def leaveEvent(self, _):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        h = self._hit(e.position())
        if h is not None:
            self.itemClicked.emit(self.items[h].key)


class YearView(QWidget):
    daySelected = Signal(object)
    weekClicked = Signal(object)
    monthClicked = Signal(int, int)
    weekdayClicked = Signal(int, int)  # weekday, year

    def __init__(self, store: Store, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self.year = date.today().year
        self.selected = date.today()

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 32)
        root.setSpacing(18)

        # header
        head = QHBoxLayout()
        head.setSpacing(6)
        self.title = label("", "h1")
        prev_b = icon_button("‹", "Previous year")
        next_b = icon_button("›", "Next year")
        for b in (prev_b, next_b):
            b.setStyleSheet("font-size:20px;")
        prev_b.clicked.connect(lambda: self.set_year(self.year - 1))
        next_b.clicked.connect(lambda: self.set_year(self.year + 1))
        head.addWidget(prev_b, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(next_b, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addSpacing(10)
        head.addWidget(self.title)
        head.addStretch(1)
        head.addWidget(Legend(), 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(head)

        # stat tiles
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t_avg = StatTile("Year average")
        self.t_logged = StatTile("Days logged")
        self.t_best = StatTile("Best weekday")
        self.t_worst = StatTile("Toughest weekday")
        self.t_calm = StatTile("Calmest weekday")
        for t in (self.t_avg, self.t_logged, self.t_best, self.t_worst, self.t_calm):
            tiles.addWidget(t, 1)
        root.addLayout(tiles)

        # heatmap card
        card = Card(margins=20)
        card.body.addWidget(caps("Every day"))
        self.heatmap = YearHeatmap(store)
        self.heatmap.daySelected.connect(self.daySelected)
        self.heatmap.weekClicked.connect(self.weekClicked)
        self.heatmap.weekdayClicked.connect(lambda wd: self.weekdayClicked.emit(wd, self.year))
        card.body.addWidget(self.heatmap)
        root.addWidget(card)

        # months
        mcard = Card(margins=20)
        mcard.body.addWidget(caps("Months"))
        self.months = SummaryStrip(118)
        self.months.itemClicked.connect(lambda m: self.monthClicked.emit(self.year, m))
        mcard.body.addWidget(self.months)
        root.addWidget(mcard)

        # years
        self.ycard = Card(margins=20)
        self.ycard.body.addWidget(caps("Years"))
        self.years = SummaryStrip(100)
        self.years.itemClicked.connect(self.set_year)
        self.ycard.body.addWidget(self.years)
        root.addWidget(self.ycard)
        root.addStretch(1)

        store.changed.connect(lambda _d: self.refresh())
        self.refresh()

    def set_year(self, year: int) -> None:
        self.year = year
        self.refresh()

    def set_selected(self, d: date) -> None:
        self.selected = d
        if d.year != self.year:
            self.year = d.year
            self.refresh()
        self.heatmap.set_selected(d)

    def refresh(self) -> None:
        y = self.year
        self.title.setText(str(y))
        self.heatmap.set_year(y)
        self.heatmap.set_selected(self.selected)
        entries = self.store.between(date(y, 1, 1), date(y, 12, 31))
        summary = stats.summarize(e.score for e in entries)

        today = date.today()
        span = 366 if calendar.isleap(y) else 365
        if y == today.year:
            span = today.timetuple().tm_yday
        elif y > today.year:
            span = 0
        if summary.mean is not None:
            self.t_avg.set(f"{summary.mean:.1f}", SCORE_WORDS[round(summary.mean)], summary.mean)
        else:
            self.t_avg.set("–", "No ratings yet")
        self.t_logged.set(str(len(entries)), f"of {span} days so far" if span else "")

        wd = stats.by_weekday(entries)
        rated = [(i, s) for i, s in enumerate(wd) if s.mean is not None and s.count >= 2]
        if rated:
            best = max(rated, key=lambda x: x[1].mean)
            worst = min(rated, key=lambda x: x[1].mean)
            calm = min(rated, key=lambda x: x[1].std)
            wild = max(rated, key=lambda x: x[1].std)
            self.t_best.set(
                WEEKDAYS[best[0]], f"avg {best[1].mean:.1f} over {best[1].count} days", best[1].mean
            )
            self.t_worst.set(
                WEEKDAYS[worst[0]],
                f"avg {worst[1].mean:.1f} over {worst[1].count} days",
                worst[1].mean,
            )
            self.t_calm.set(
                WEEKDAYS[calm[0]],
                f"±{calm[1].std:.1f} swing · wildest: {WEEKDAYS_SHORT[wild[0]]} ±{wild[1].std:.1f}",
            )
        else:
            for t in (self.t_best, self.t_worst, self.t_calm):
                t.set("–", "Needs a few more days")

        # months strip
        items = []
        for m in range(1, 13):
            ndays = calendar.monthrange(y, m)[1]
            spark = [self.store.score(date(y, m, k)) for k in range(1, ndays + 1)]
            ms = stats.summarize(spark)
            items.append(
                StripItem(
                    m,
                    MONTHS_SHORT[m - 1],
                    ms.mean,
                    f"{ms.count} days" if ms.count else "",
                    spark,
                    highlight=(y == self.selected.year and m == self.selected.month),
                )
            )
        self.months.set_items(items)

        # years strip
        by_year = stats.by_year(self.store.all())
        years = sorted(set(by_year) | {today.year, y})
        yitems = []
        for yy in years:
            s = by_year.get(yy)
            spark = [
                ms.mean
                for ms in stats.by_month(self.store.between(date(yy, 1, 1), date(yy, 12, 31)), yy)
            ]
            yitems.append(
                StripItem(
                    yy,
                    str(yy),
                    s.mean if s else None,
                    f"{s.count} days" if s else "",
                    spark,
                    highlight=yy == y,
                )
            )
        self.years.set_items(yitems[-8:])
        self.update()


__all__ = ["QPen", "StripItem", "SummaryStrip", "YearView", "text_on", "tooltip_html"]
