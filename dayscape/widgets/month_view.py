"""Month view: big calendar grid with note previews and weekly averages."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QHBoxLayout, QToolTip, QVBoxLayout, QWidget

from dayscape import stats
from dayscape.models import MONTHS, SCORE_WORDS, WEEKDAYS_SHORT
from dayscape.store import Store
from dayscape.theme import C, font, score_color, tint
from dayscape.widgets.common import (
    Legend,
    StatTile,
    elide,
    fill_round,
    icon_button,
    label,
    score_badge,
    score_pill,
    stroke_round,
)
from dayscape.widgets.year_view import tooltip_html


def month_weeks(year: int, month: int) -> list[date]:
    """Mondays of every week that touches the month."""
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    start = first - timedelta(days=first.weekday())
    out = []
    while start <= last:
        out.append(start)
        start += timedelta(weeks=1)
    return out


class MonthGrid(QWidget):
    daySelected = Signal(object)
    dayActivated = Signal(object)
    weekClicked = Signal(object)

    HEADER = 30
    WEEK_COL = 70
    GAP = 8

    def __init__(self, store: Store, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self.year, self.month = date.today().year, date.today().month
        self.selected: date | None = None
        self._hover: tuple[str, object] | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(self.HEADER + 5 * 40)

    def set_month(self, year: int, month: int) -> None:
        self.year, self.month = year, month
        self.update()

    def set_selected(self, d: date) -> None:
        self.selected = d
        self.update()

    # geometry -----------------------------------------------------------------
    def weeks(self) -> list[date]:
        return month_weeks(self.year, self.month)

    def col_w(self) -> float:
        return (self.width() - self.WEEK_COL - self.GAP * 7) / 7

    def row_h(self) -> float:
        return (self.height() - self.HEADER - self.GAP * (len(self.weeks()) - 1)) / len(
            self.weeks()
        )

    def cell_rect(self, row: int, col: int) -> QRectF:
        cw, rh = self.col_w(), self.row_h()
        return QRectF(col * (cw + self.GAP), self.HEADER + row * (rh + self.GAP), cw, rh)

    def week_rect(self, row: int) -> QRectF:
        rh = self.row_h()
        x = 7 * (self.col_w() + self.GAP)
        return QRectF(x, self.HEADER + row * (rh + self.GAP), self.WEEK_COL, rh)

    # painting -----------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        today = date.today()
        weeks = self.weeks()

        p.setFont(font(11, QFont.Weight.DemiBold))
        for c in range(7):
            r = self.cell_rect(0, c)
            p.setPen(QColor(C.TEXT_DIM if c == today.weekday() else C.TEXT_FAINT))
            p.drawText(
                QRectF(r.left() + 4, 0, r.width(), self.HEADER - 8),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                WEEKDAYS_SHORT[c].upper(),
            )
        wr = self.week_rect(0)
        p.setPen(QColor(C.TEXT_FAINT))
        p.drawText(
            QRectF(wr.left(), 0, wr.width(), self.HEADER - 8), Qt.AlignmentFlag.AlignCenter, "WEEK"
        )

        for row, monday in enumerate(weeks):
            for col in range(7):
                d = monday + timedelta(days=col)
                self._paint_day(p, self.cell_rect(row, col), d, today)
            self._paint_week(p, row, monday)
        p.end()

    def _paint_day(self, p: QPainter, r: QRectF, d: date, today: date) -> None:
        in_month = d.month == self.month
        e = self.store.get(d)
        score = e.score if e else None
        if in_month:
            fill_round(
                p, r, 12, tint(score, 0.17) if score else (C.SURFACE if d <= today else C.BG)
            )
            if score:
                bar = QRectF(r.left(), r.top() + 12, 3.5, r.height() - 24)
                fill_round(p, bar, 1.75, score_color(score))
        else:
            stroke_round(p, r, 12, C.SURFACE_2, 1.0)

        hovered = self._hover == ("day", d)
        if d == self.selected:
            stroke_round(p, r, 12, C.ACCENT, 2.0)
        elif hovered:
            stroke_round(p, r, 12, C.BORDER_STRONG, 1.2)
        elif in_month and not score:
            stroke_round(p, r, 12, C.BORDER, 1.0)

        # day number
        p.setFont(font(13, QFont.Weight.DemiBold))
        txt = str(d.day)
        if d == today:
            w = p.fontMetrics().horizontalAdvance(txt) + 14
            pill = QRectF(r.left() + 7, r.top() + 9, w, 24)
            fill_round(p, pill, 8, C.ACCENT)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, txt)
        else:
            p.setPen(QColor(C.TEXT if in_month else C.TEXT_FAINT))
            p.drawText(
                QRectF(r.left() + 14, r.top() + 9, 40, 24),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                txt,
            )
        if not in_month:
            return
        if score:
            score_badge(p, QPointF(r.right() - 22, r.top() + 21), 26, score)

        # note preview lines
        if e and e.lines:
            p.setFont(font(12))
            fm = p.fontMetrics()
            lh = fm.height() + 2
            top = r.top() + 40
            avail = int((r.bottom() - 8 - top) // lh)
            lines = e.lines
            show = lines if len(lines) <= avail else lines[: max(0, avail - 1)]
            for i, ln in enumerate(show):
                p.setPen(QColor(C.TEXT_DIM))
                p.drawText(
                    QRectF(r.left() + 14, top + i * lh, r.width() - 24, lh),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    elide(p, ln, r.width() - 24),
                )
            rest = len(lines) - len(show)
            if rest > 0 and avail > 0:
                p.setPen(QColor(C.TEXT_FAINT))
                p.drawText(
                    QRectF(r.left() + 14, top + len(show) * lh, r.width() - 24, lh),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"+{rest} more",
                )

    def _paint_week(self, p: QPainter, row: int, monday: date) -> None:
        r = self.week_rect(row)
        scores = [self.store.score(monday + timedelta(days=i)) for i in range(7)]
        s = stats.summarize(scores)
        if self._hover == ("week", row):
            fill_round(p, r, 12, C.SURFACE)
        pill = QRectF(r.center().x() - 24, r.center().y() - 16, 48, 24)
        score_pill(p, pill, s.mean)
        p.setFont(font(10, QFont.Weight.DemiBold))
        p.setPen(QColor(C.TEXT_FAINT))
        p.drawText(
            QRectF(r.left(), pill.bottom() + 4, r.width(), 16),
            Qt.AlignmentFlag.AlignCenter,
            f"W{monday.isocalendar()[1]}",
        )

    # interaction -------------------------------------------------------------
    def _hit(self, pos: QPointF):
        for row, monday in enumerate(self.weeks()):
            for col in range(7):
                if self.cell_rect(row, col).contains(pos):
                    return ("day", monday + timedelta(days=col))
            if self.week_rect(row).contains(pos):
                return ("week", row)
        return None

    def mouseMoveEvent(self, e):
        hit = self._hit(e.position())
        if hit != self._hover:
            self._hover = hit
            self.setCursor(Qt.CursorShape.PointingHandCursor if hit else Qt.CursorShape.ArrowCursor)
            self.update()
        if hit and hit[0] == "day":
            ent = self.store.get(hit[1])
            if ent and len(ent.lines) > 2:
                QToolTip.showText(
                    e.globalPosition().toPoint(), tooltip_html(hit[1], ent.score, ent.lines), self
                )
                return
        QToolTip.hideText()

    def leaveEvent(self, _):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        hit = self._hit(e.position())
        if not hit or e.button() != Qt.MouseButton.LeftButton:
            return
        if hit[0] == "day":
            self.daySelected.emit(hit[1])
        else:
            self.weekClicked.emit(self.weeks()[hit[1]])

    def mouseDoubleClickEvent(self, e):
        hit = self._hit(e.position())
        if hit and hit[0] == "day":
            self.dayActivated.emit(hit[1])


class MonthView(QWidget):
    daySelected = Signal(object)
    dayActivated = Signal(object)
    weekClicked = Signal(object)

    def __init__(self, store: Store, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        t = date.today()
        self.year, self.month = t.year, t.month
        self.selected = t

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 28)
        root.setSpacing(18)

        head = QHBoxLayout()
        head.setSpacing(6)
        self.title = label("", "h1")
        prev_b = icon_button("‹", "Previous month")
        next_b = icon_button("›", "Next month")
        for b in (prev_b, next_b):
            b.setStyleSheet("font-size:20px;")
        prev_b.clicked.connect(lambda: self.shift(-1))
        next_b.clicked.connect(lambda: self.shift(1))
        head.addWidget(prev_b, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(next_b, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addSpacing(10)
        head.addWidget(self.title)
        head.addStretch(1)
        head.addWidget(Legend(), 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(head)

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t_avg = StatTile("Month average")
        self.t_logged = StatTile("Days logged")
        self.t_best = StatTile("Best day")
        self.t_worst = StatTile("Toughest day")
        self.t_trend = StatTile("Versus last month")
        for tile in (self.t_avg, self.t_logged, self.t_best, self.t_worst, self.t_trend):
            tiles.addWidget(tile, 1)
        root.addLayout(tiles)

        self.grid = MonthGrid(store)
        self.grid.daySelected.connect(self.daySelected)
        self.grid.dayActivated.connect(self.dayActivated)
        self.grid.weekClicked.connect(self.weekClicked)
        root.addWidget(self.grid, 1)

        store.changed.connect(lambda _d: self.refresh())
        self.refresh()

    def shift(self, delta: int) -> None:
        m = self.month - 1 + delta
        self.year += m // 12
        self.month = m % 12 + 1
        self.refresh()

    def set_month(self, year: int, month: int) -> None:
        self.year, self.month = year, month
        self.refresh()

    def set_selected(self, d: date) -> None:
        self.selected = d
        if (d.year, d.month) != (self.year, self.month):
            self.year, self.month = d.year, d.month
            self.refresh()
        self.grid.set_selected(d)

    def _month_entries(self, year: int, month: int):
        last = calendar.monthrange(year, month)[1]
        return self.store.between(date(year, month, 1), date(year, month, last))

    def refresh(self) -> None:
        self.title.setText(f"{MONTHS[self.month - 1]} {self.year}")
        self.grid.set_month(self.year, self.month)
        self.grid.set_selected(self.selected)
        entries = self._month_entries(self.year, self.month)
        s = stats.summarize(e.score for e in entries)
        days_in = calendar.monthrange(self.year, self.month)[1]
        if s.mean is not None:
            self.t_avg.set(f"{s.mean:.1f}", SCORE_WORDS[round(s.mean)], s.mean)
        else:
            self.t_avg.set("–", "No ratings yet")
        self.t_logged.set(str(len(entries)), f"of {days_in} days")

        rated = [e for e in entries if e.score is not None]
        if rated:
            best = max(rated, key=lambda e: (e.score, e.day))
            worst = min(rated, key=lambda e: (e.score, -e.day.toordinal()))
            self.t_best.set(
                f"{WEEKDAYS_SHORT[best.day.weekday()]} {best.day.day}",
                (best.lines[0] if best.lines else f"scored {best.score}"),
                best.score,
            )
            self.t_worst.set(
                f"{WEEKDAYS_SHORT[worst.day.weekday()]} {worst.day.day}",
                (worst.lines[0] if worst.lines else f"scored {worst.score}"),
                worst.score,
            )
        else:
            self.t_best.set("–", "")
            self.t_worst.set("–", "")

        py, pm = (self.year, self.month - 1) if self.month > 1 else (self.year - 1, 12)
        prev = stats.summarize(e.score for e in self._month_entries(py, pm))
        if s.mean is not None and prev.mean is not None:
            delta = s.mean - prev.mean
            arrow = "▲" if delta > 0.05 else "▼" if delta < -0.05 else "■"
            color = "#6CC67C" if delta > 0.05 else "#EA6A48" if delta < -0.05 else C.TEXT_DIM
            self.t_trend.set(
                f"{arrow} {abs(delta):.1f}", f"{MONTHS[pm - 1]} averaged {prev.mean:.1f}"
            )
            self.t_trend.value.setStyleSheet(f"color:{color};")
        else:
            self.t_trend.set("–", "Not enough data")
            self.t_trend.value.setStyleSheet("")
