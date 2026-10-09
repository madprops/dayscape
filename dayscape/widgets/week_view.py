"""Week view: seven day cards side by side, each compared to your usual weekday."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from dayscape import stats
from dayscape.models import MONTHS, MONTHS_SHORT, SCORE_WORDS, WEEKDAYS
from dayscape.store import Store
from dayscape.theme import C, font, score_color, tint
from dayscape.widgets.common import (
    Legend,
    StatTile,
    fill_round,
    icon_button,
    label,
    score_badge,
    stroke_round,
)


class WeekBoard(QWidget):
    daySelected = Signal(object)
    dayActivated = Signal(object)

    GAP = 12

    def __init__(self, store: Store, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self.monday = stats.week_start(date.today())
        self.selected: date | None = None
        self._hover: int | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(200)

    def set_week(self, monday: date) -> None:
        self.monday = monday
        self.update()

    def set_selected(self, d: date) -> None:
        self.selected = d
        self.update()

    def card_rect(self, i: int) -> QRectF:
        w = (self.width() - self.GAP * 6) / 7
        return QRectF(i * (w + self.GAP), 0, w, self.height())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        today = date.today()
        weekday_means = stats.by_weekday(self.store.all())
        for i in range(7):
            d = self.monday + timedelta(days=i)
            r = self.card_rect(i)
            e = self.store.get(d)
            score = e.score if e else None
            fill_round(p, r, 16, tint(score, 0.13, C.SURFACE) if score else C.SURFACE)
            if score:
                fill_round(
                    p, QRectF(r.left() + 16, r.top(), r.width() - 32, 3), 1.5, score_color(score)
                )
            if d == self.selected:
                stroke_round(p, r, 16, C.ACCENT, 2.0)
            elif self._hover == i:
                stroke_round(p, r, 16, C.BORDER_STRONG, 1.2)
            else:
                stroke_round(p, r, 16, C.BORDER, 1.0)

            inner = r.adjusted(16, 18, -16, -16)
            p.setFont(font(11, QFont.Weight.DemiBold, 1.2))
            p.setPen(QColor(C.ACCENT_GLOW if d == today else C.TEXT_FAINT))
            p.drawText(
                inner,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                WEEKDAYS[i].upper() + ("  · TODAY" if d == today and inner.width() > 130 else ""),
            )
            p.setFont(font(17, QFont.Weight.DemiBold))
            p.setPen(QColor(C.TEXT))
            p.drawText(
                QRectF(inner.left(), inner.top() + 18, inner.width(), 26),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{MONTHS_SHORT[d.month - 1]} {d.day}",
            )

            # score
            y = inner.top() + 60
            if score:
                score_badge(p, QPointF(inner.left() + 24, y + 24), 48, score)
                p.setFont(font(13, QFont.Weight.DemiBold))
                p.setPen(score_color(score))
                p.drawText(
                    QRectF(inner.left() + 58, y + 4, inner.width() - 58, 22),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    SCORE_WORDS[score],
                )
                usual = weekday_means[i].mean
                if usual is not None:
                    delta = score - usual
                    col = (
                        "#6CC67C" if delta > 0.25 else "#EA6A48" if delta < -0.25 else C.TEXT_FAINT
                    )
                    sign = "+" if delta >= 0 else "−"
                    p.setFont(font(11))
                    p.setPen(QColor(col))
                    p.drawText(
                        QRectF(inner.left() + 58, y + 24, inner.width() - 58, 20),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        f"{sign}{abs(delta):.1f} vs usual",
                    )
            else:
                pen = QPen(QColor(C.BORDER_STRONG), 1.4, Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(inner.left() + 24, y + 24), 23, 23)
                p.setFont(font(12))
                p.setPen(QColor(C.TEXT_FAINT))
                p.drawText(
                    QRectF(inner.left() + 58, y + 14, inner.width() - 58, 22),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    "Not rated" if d <= today else "Upcoming",
                )

            # notes
            ny = y + 66
            p.setPen(QPen(QColor(C.BORDER), 1))
            p.drawLine(QPointF(inner.left(), ny), QPointF(inner.right(), ny))
            ny += 12
            if e and e.lines:
                p.setFont(font(13))
                for ln in e.lines:
                    box = QRectF(inner.left() + 12, ny, inner.width() - 12, inner.bottom() - ny)
                    br = p.boundingRect(box, Qt.TextFlag.TextWordWrap, ln)
                    if br.bottom() > inner.bottom():
                        p.setPen(QColor(C.TEXT_FAINT))
                        p.drawText(
                            QRectF(inner.left(), inner.bottom() - 18, inner.width(), 18),
                            Qt.AlignmentFlag.AlignLeft,
                            "…",
                        )
                        break
                    p.setBrush(score_color(score) if score else QColor(C.TEXT_FAINT))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(
                        QPointF(inner.left() + 3, ny + p.fontMetrics().height() / 2), 2.2, 2.2
                    )
                    p.setPen(QColor(C.TEXT_DIM))
                    p.drawText(box, Qt.TextFlag.TextWordWrap, ln)
                    ny = br.bottom() + 7
            elif d <= today:
                p.setFont(font(12))
                p.setPen(QColor(C.TEXT_FAINT))
                p.drawText(
                    QRectF(inner.left(), ny, inner.width(), 40),
                    Qt.TextFlag.TextWordWrap,
                    "Click to add notes",
                )
        p.end()

    def _hit(self, pos: QPointF) -> int | None:
        for i in range(7):
            if self.card_rect(i).contains(pos):
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
        if h is not None and e.button() == Qt.MouseButton.LeftButton:
            self.daySelected.emit(self.monday + timedelta(days=h))

    def mouseDoubleClickEvent(self, e):
        h = self._hit(e.position())
        if h is not None:
            self.dayActivated.emit(self.monday + timedelta(days=h))


class WeekView(QWidget):
    daySelected = Signal(object)
    dayActivated = Signal(object)

    def __init__(self, store: Store, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self.selected = date.today()
        self.monday = stats.week_start(self.selected)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 28)
        root.setSpacing(18)

        head = QHBoxLayout()
        head.setSpacing(6)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.title = label("", "h1")
        self.subtitle = label("", "muted")
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        prev_b = icon_button("‹", "Previous week  (Alt+↑)")
        next_b = icon_button("›", "Next week  (Alt+↓)")
        for b in (prev_b, next_b):
            b.setStyleSheet("font-size:20px;")
        prev_b.clicked.connect(lambda: self.set_week(self.monday - timedelta(weeks=1)))
        next_b.clicked.connect(lambda: self.set_week(self.monday + timedelta(weeks=1)))
        head.addWidget(prev_b, 0, Qt.AlignmentFlag.AlignTop)
        head.addWidget(next_b, 0, Qt.AlignmentFlag.AlignTop)
        head.addSpacing(10)
        head.addLayout(titles)
        head.addStretch(1)
        head.addWidget(Legend(), 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(head)

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t_avg = StatTile("Week average")
        self.t_prev = StatTile("Versus last week")
        self.t_range = StatTile("Range")
        self.t_logged = StatTile("Days logged")
        for t in (self.t_avg, self.t_prev, self.t_range, self.t_logged):
            tiles.addWidget(t, 1)
        root.addLayout(tiles)

        self.board = WeekBoard(store)
        self.board.daySelected.connect(self.daySelected)
        self.board.dayActivated.connect(self.dayActivated)
        root.addWidget(self.board, 1)

        store.changed.connect(lambda _d: self.refresh())
        self.refresh()

    def set_week(self, monday: date) -> None:
        self.monday = monday
        self.refresh()

    def set_selected(self, d: date) -> None:
        self.selected = d
        m = stats.week_start(d)
        if m != self.monday:
            self.monday = m
            self.refresh()
        self.board.set_selected(d)

    def refresh(self) -> None:
        m = self.monday
        sun = m + timedelta(days=6)
        iso = m.isocalendar()
        self.title.setText(f"Week {iso[1]}")
        if m.month == sun.month:
            sub = f"{m.day} – {sun.day} {MONTHS[m.month - 1]} {sun.year}"
        else:
            sub = f"{m.day} {MONTHS_SHORT[m.month - 1]} – {sun.day} {MONTHS_SHORT[sun.month - 1]} {sun.year}"
        self.subtitle.setText(sub)
        self.board.set_week(m)
        self.board.set_selected(self.selected)

        entries = self.store.between(m, sun)
        s = stats.summarize(e.score for e in entries)
        prev = stats.summarize(
            e.score for e in self.store.between(m - timedelta(weeks=1), m - timedelta(days=1))
        )
        if s.mean is not None:
            self.t_avg.set(f"{s.mean:.1f}", SCORE_WORDS[round(s.mean)], s.mean)
            self.t_range.set(
                f"{s.low} – {s.high}",
                "calm week" if s.std < 1.0 else "bumpy week" if s.std > 2 else "some ups and downs",
            )
        else:
            self.t_avg.set("–", "No ratings yet")
            self.t_range.set("–", "")
        if s.mean is not None and prev.mean is not None:
            delta = s.mean - prev.mean
            arrow = "▲" if delta > 0.05 else "▼" if delta < -0.05 else "■"
            color = "#6CC67C" if delta > 0.05 else "#EA6A48" if delta < -0.05 else C.TEXT_DIM
            self.t_prev.set(f"{arrow} {abs(delta):.1f}", f"last week averaged {prev.mean:.1f}")
            self.t_prev.value.setStyleSheet(f"color:{color};")
        else:
            self.t_prev.set("–", "Not enough data")
            self.t_prev.value.setStyleSheet("")
        self.t_logged.set(f"{len(entries)} / 7", "")
