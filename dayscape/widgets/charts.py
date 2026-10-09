"""Custom QPainter charts for the Insights dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from dayscape.models import MONTHS_SHORT, WEEKDAYS, WEEKDAYS_SHORT, format_long
from dayscape.stats import Summary
from dayscape.theme import C, font, qc, score_color, text_on
from dayscape.widgets.common import elide, fill_round, score_pill


def _grid(p: QPainter, plot: QRectF, lo: float, hi: float, ticks: list[float], fmt=str) -> None:
    p.setFont(font(10))
    for t in ticks:
        y = plot.bottom() - (t - lo) / (hi - lo) * plot.height()
        p.setPen(QPen(QColor(C.BORDER), 1, Qt.PenStyle.DotLine))
        p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        p.setPen(QColor(C.TEXT_FAINT))
        p.drawText(
            QRectF(0, y - 8, plot.left() - 8, 16),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            fmt(t),
        )


class WeekdayChart(QWidget):
    """Average per weekday with a ±1σ whisker — tall bar = good, long whisker = unpredictable."""

    weekdayClicked = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.data: list[Summary] = [Summary() for _ in range(7)]
        self._hover: int | None = None
        self.setMinimumHeight(250)
        self.setMouseTracking(True)

    def set_data(self, data: list[Summary]) -> None:
        self.data = data
        self.update()

    def _plot(self) -> QRectF:
        return QRectF(30, 26, self.width() - 34, self.height() - 26 - 46)

    def _bar(self, i: int) -> QRectF:
        plot = self._plot()
        slot = plot.width() / 7
        bw = min(54.0, slot * 0.56)
        return QRectF(plot.left() + i * slot + (slot - bw) / 2, plot.top(), bw, plot.height())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self._plot()
        _grid(p, plot, 0, 10, [0, 2, 4, 6, 8, 10], lambda t: str(int(t)))
        means = [s.mean for s in self.data if s.mean is not None]
        best = max(means) if means else None
        worst = min(means) if means else None

        for i, s in enumerate(self.data):
            slot = self._bar(i)
            if s.mean is not None:
                h = s.mean / 10 * plot.height()
                bar = QRectF(slot.left(), plot.bottom() - h, slot.width(), h)
                col = score_color(s.mean)
                grad = QLinearGradient(bar.topLeft(), bar.bottomLeft())
                grad.setColorAt(0, col)
                c2 = QColor(col)
                c2.setAlpha(70 if self._hover != i else 120)
                grad.setColorAt(1, c2)
                path = QPainterPath()
                path.addRoundedRect(bar, 8, 8)
                p.fillPath(path, grad)

                # whisker ±1σ
                if s.std is not None and s.count > 1:
                    cx = bar.center().x()
                    top = plot.bottom() - min(10, s.mean + s.std) / 10 * plot.height()
                    bot = plot.bottom() - max(0, s.mean - s.std) / 10 * plot.height()
                    p.setPen(QPen(qc(C.TEXT, 150), 1.4))
                    p.drawLine(QPointF(cx, top), QPointF(cx, bot))
                    p.drawLine(QPointF(cx - 6, top), QPointF(cx + 6, top))
                    p.drawLine(QPointF(cx - 6, bot), QPointF(cx + 6, bot))

                # value label
                p.setFont(font(12, QFont.Weight.Bold))
                p.setPen(col)
                p.drawText(
                    QRectF(slot.left() - 20, bar.top() - 22, slot.width() + 40, 18),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{s.mean:.1f}",
                )
            # x labels
            is_best = s.mean is not None and s.mean == best and best != worst
            is_worst = s.mean is not None and s.mean == worst and best != worst
            p.setFont(font(12, QFont.Weight.DemiBold))
            p.setPen(QColor(C.TEXT if self._hover == i else C.TEXT_DIM))
            p.drawText(
                QRectF(slot.left() - 20, plot.bottom() + 8, slot.width() + 40, 18),
                Qt.AlignmentFlag.AlignCenter,
                WEEKDAYS_SHORT[i],
            )
            p.setFont(font(10))
            sub = "best" if is_best else "toughest" if is_worst else f"{s.count} days"
            p.setPen(QColor(C.ACCENT_GLOW if is_best else "#EA6A48" if is_worst else C.TEXT_FAINT))
            p.drawText(
                QRectF(slot.left() - 20, plot.bottom() + 26, slot.width() + 40, 16),
                Qt.AlignmentFlag.AlignCenter,
                sub,
            )
        p.end()

    def _hit(self, pos: QPointF) -> int | None:
        plot = self._plot()
        if plot.left() <= pos.x() <= plot.right():
            return min(6, int((pos.x() - plot.left()) // (plot.width() / 7)))
        return None

    def mouseMoveEvent(self, e):
        h = self._hit(e.position())
        if h != self._hover:
            self._hover = h
            self.update()
        if h is None:
            QToolTip.hideText()
            return
        s = self.data[h]
        if s.mean is None:
            txt = f"<b>{WEEKDAYS[h]}</b><br>No ratings in range"
        else:
            txt = (
                f"<b>{WEEKDAYS[h]}</b> · {s.count} days<br>average <b>{s.mean:.2f}</b>"
                f"<br>swing ±{s.std:.2f} · range {s.low}–{s.high}<br>"
                f"<span style='color:{C.TEXT_FAINT}'>Click to list these days</span>"
            )
        QToolTip.showText(e.globalPosition().toPoint(), txt, self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def leaveEvent(self, _):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        h = self._hit(e.position())
        if h is not None:
            self.weekdayClicked.emit(h)


class DistributionChart(QWidget):
    scoreClicked = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.counts = [0] * 10
        self._hover: int | None = None
        self.setMinimumHeight(250)
        self.setMouseTracking(True)

    def set_data(self, counts: list[int]) -> None:
        self.counts = counts
        self.update()

    def _plot(self) -> QRectF:
        return QRectF(8, 26, self.width() - 16, self.height() - 26 - 28)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self._plot()
        top = max(self.counts) or 1
        total = sum(self.counts) or 1
        slot = plot.width() / 10
        for i, n in enumerate(self.counts):
            bw = slot * 0.7
            x = plot.left() + i * slot + (slot - bw) / 2
            h = max(3.0, n / top * plot.height()) if n else 3.0
            bar = QRectF(x, plot.bottom() - h, bw, h)
            col = score_color(i + 1)
            if not n:
                col = QColor(C.EMPTY)
            elif self._hover is not None and self._hover != i:
                col.setAlpha(110)
            fill_round(p, bar, 5, col)
            if n:
                p.setFont(font(10, QFont.Weight.DemiBold))
                p.setPen(QColor(C.TEXT_DIM))
                p.drawText(
                    QRectF(x - 10, bar.top() - 18, bw + 20, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{round(100 * n / total)}%",
                )
            p.setFont(font(11, QFont.Weight.DemiBold))
            p.setPen(QColor(C.TEXT_DIM))
            p.drawText(
                QRectF(x - 10, plot.bottom() + 6, bw + 20, 18),
                Qt.AlignmentFlag.AlignCenter,
                str(i + 1),
            )
        p.end()

    def _hit(self, pos: QPointF) -> int | None:
        plot = self._plot()
        if plot.left() <= pos.x() <= plot.right():
            return min(9, int((pos.x() - plot.left()) // (plot.width() / 10)))
        return None

    def mouseMoveEvent(self, e):
        h = self._hit(e.position())
        if h != self._hover:
            self._hover = h
            self.update()
        if h is not None:
            n = self.counts[h]
            QToolTip.showText(
                e.globalPosition().toPoint(),
                f"<b>{n}</b> day{'s' if n != 1 else ''} scored <b>{h + 1}</b>",
                self,
            )
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def leaveEvent(self, _):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        h = self._hit(e.position())
        if h is not None:
            self.scoreClicked.emit(h + 1)


class TrendChart(QWidget):
    """Daily dots + smoothed rolling averages over a date range."""

    daySelected = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.start = date.today() - timedelta(days=90)
        self.end = date.today()
        self.points: list[tuple[date, int]] = []
        self.short: list[tuple[date, float]] = []
        self.long: list[tuple[date, float]] = []
        self._hover: date | None = None
        self.setMinimumHeight(260)
        self.setMouseTracking(True)

    def set_data(self, start, end, points, short, long) -> None:
        self.start, self.end = start, end
        self.points, self.short, self.long = points, short, long
        self.update()

    def _plot(self) -> QRectF:
        return QRectF(30, 14, self.width() - 38, self.height() - 14 - 28)

    def _x(self, d: date, plot: QRectF) -> float:
        span = max(1, (self.end - self.start).days)
        return plot.left() + (d - self.start).days / span * plot.width()

    def _y(self, v: float, plot: QRectF) -> float:
        return plot.bottom() - (v - 1) / 9 * plot.height()

    def _path(self, series, plot: QRectF) -> QPainterPath:
        path = QPainterPath()
        prev: QPointF | None = None
        prev_d: date | None = None
        for d, v in series:
            pt = QPointF(self._x(d, plot), self._y(v, plot))
            if prev is None or (prev_d and (d - prev_d).days > 3):
                path.moveTo(pt)
            else:
                mx = (prev.x() + pt.x()) / 2
                path.cubicTo(QPointF(mx, prev.y()), QPointF(mx, pt.y()), pt)
            prev, prev_d = pt, d
        return path

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self._plot()
        _grid(p, plot, 1, 10, [1, 4, 7, 10], lambda t: str(int(t)))

        # month ticks
        span = (self.end - self.start).days
        p.setFont(font(10))
        d = date(self.start.year, self.start.month, 1)
        step_months = 1 if span <= 400 else 3 if span <= 1200 else 12
        while d <= self.end:
            if d >= self.start:
                x = self._x(d, plot)
                p.setPen(QPen(QColor(C.BORDER), 1))
                p.drawLine(QPointF(x, plot.bottom()), QPointF(x, plot.bottom() + 4))
                p.setPen(QColor(C.TEXT_FAINT))
                lbl = (
                    MONTHS_SHORT[d.month - 1] if d.month != 1 and step_months < 12 else str(d.year)
                )
                p.drawText(QPointF(x + 3, plot.bottom() + 18), lbl)
            m = d.month - 1 + step_months
            d = date(d.year + m // 12, m % 12 + 1, 1)
        if span <= 45:
            # weekly ticks for short ranges
            k = self.start + timedelta(days=(7 - self.start.weekday()) % 7)
            while k <= self.end:
                x = self._x(k, plot)
                p.setPen(QColor(C.TEXT_FAINT))
                p.drawText(QPointF(x + 3, plot.bottom() + 18), f"{k.day}")
                k += timedelta(weeks=1)

        # daily dots
        r = 3.2 if span <= 120 else 2.4 if span <= 400 else 1.6
        p.setPen(Qt.PenStyle.NoPen)
        for d, v in self.points:
            c = score_color(v)
            c.setAlpha(170)
            p.setBrush(c)
            p.drawEllipse(QPointF(self._x(d, plot), self._y(v, plot)), r, r)

        # long average (soft)
        if self.long:
            p.setPen(QPen(qc(C.TEXT, 120), 1.6, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(self._path(self.long, plot))

        # short average (accent, with glow fill)
        if self.short:
            path = self._path(self.short, plot)
            fill = QPainterPath(path)
            fill.lineTo(QPointF(self._x(self.short[-1][0], plot), plot.bottom()))
            fill.lineTo(QPointF(self._x(self.short[0][0], plot), plot.bottom()))
            fill.closeSubpath()
            grad = QLinearGradient(QPointF(0, plot.top()), QPointF(0, plot.bottom()))
            grad.setColorAt(0, qc(C.ACCENT, 70))
            grad.setColorAt(1, qc(C.ACCENT, 0))
            p.fillPath(fill, grad)
            p.setPen(
                QPen(QColor(C.ACCENT_GLOW), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            )
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        # hover crosshair
        if self._hover:
            x = self._x(self._hover, plot)
            p.setPen(QPen(qc(C.TEXT, 70), 1))
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            v = dict(self.points).get(self._hover)
            if v:
                p.setBrush(score_color(v))
                p.setPen(QPen(QColor(C.BG), 2))
                p.drawEllipse(QPointF(x, self._y(v, plot)), 5.5, 5.5)
        p.end()

    def _date_at(self, x: float) -> date | None:
        plot = self._plot()
        if not plot.left() <= x <= plot.right():
            return None
        span = max(1, (self.end - self.start).days)
        return self.start + timedelta(days=round((x - plot.left()) / plot.width() * span))

    def mouseMoveEvent(self, e):
        d = self._date_at(e.position().x())
        if d != self._hover:
            self._hover = d
            self.update()
        if not d:
            QToolTip.hideText()
            return
        v = dict(self.points).get(d)
        sa = dict(self.short).get(d)
        la = dict(self.long).get(d)
        parts = [f"<b>{WEEKDAYS_SHORT[d.weekday()]}</b> {format_long(d)}"]
        parts.append(
            f"score <b style='color:{score_color(v).name()}'>{v}</b>"
            if v
            else f"<span style='color:{C.TEXT_FAINT}'>not rated</span>"
        )
        if sa:
            parts.append(f"<span style='color:{C.ACCENT_GLOW}'>short avg {sa:.1f}</span>")
        if la:
            parts.append(f"<span style='color:{C.TEXT_DIM}'>long avg {la:.1f}</span>")
        QToolTip.showText(e.globalPosition().toPoint(), "<br>".join(parts), self)

    def leaveEvent(self, _):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        d = self._date_at(e.position().x())
        if d:
            self.daySelected.emit(d)


@dataclass
class Row:
    key: object
    title: str
    subtitle: str
    score: float | None
    right: str = ""
    right_color: str = C.TEXT_DIM
    bar: float = 0.0  # 0..1 relative magnitude


class RowList(QWidget):
    """Compact clickable list: title · subtitle · bar · score pill · delta."""

    rowClicked = Signal(object)

    ROW_H = 34

    def __init__(self, empty_text: str = "Nothing yet", parent: QWidget | None = None):
        super().__init__(parent)
        self.rows: list[Row] = []
        self.empty_text = empty_text
        self._hover: int | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(self.ROW_H * 3)

    def set_rows(self, rows: list[Row]) -> None:
        self.rows = rows
        self.setMinimumHeight(max(3, len(rows)) * self.ROW_H)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.rows:
            p.setPen(QColor(C.TEXT_FAINT))
            p.setFont(font(12))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.empty_text)
            return
        w = self.width()
        for i, row in enumerate(self.rows):
            r = QRectF(0, i * self.ROW_H, w, self.ROW_H - 2)
            if self._hover == i:
                fill_round(p, r, 8, C.SURFACE_2)
            title_w = w * 0.30
            p.setFont(font(13, QFont.Weight.DemiBold))
            p.setPen(QColor(C.ACCENT_GLOW if row.title.startswith("#") else C.TEXT))
            p.drawText(
                QRectF(10, r.top(), title_w, r.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                elide(p, row.title, title_w),
            )
            p.setFont(font(12))
            p.setPen(QColor(C.TEXT_FAINT))
            sub_x = 10 + title_w + 8
            sub_w = w - sub_x - 140
            if row.bar > 0:
                bar_w = max(4.0, sub_w * 0.45 * row.bar)
                fill_round(p, QRectF(sub_x, r.center().y() - 3, bar_w, 6), 3, C.BORDER_STRONG)
                p.drawText(
                    QRectF(sub_x + bar_w + 8, r.top(), sub_w - bar_w - 8, r.height()),
                    Qt.AlignmentFlag.AlignVCenter,
                    elide(p, row.subtitle, sub_w - bar_w - 8),
                )
            else:
                p.setPen(QColor(C.TEXT_DIM))
                p.drawText(
                    QRectF(sub_x, r.top(), sub_w, r.height()),
                    Qt.AlignmentFlag.AlignVCenter,
                    elide(p, row.subtitle, sub_w),
                )
            score_pill(p, QRectF(w - 128, r.center().y() - 11, 46, 22), row.score)
            p.setFont(font(12, QFont.Weight.DemiBold))
            p.setPen(QColor(row.right_color))
            p.drawText(
                QRectF(w - 74, r.top(), 66, r.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                row.right,
            )
        p.end()

    def _hit(self, pos: QPointF) -> int | None:
        i = int(pos.y() // self.ROW_H)
        return i if 0 <= i < len(self.rows) else None

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
            self.rowClicked.emit(self.rows[h].key)


__all__ = ["DistributionChart", "Row", "RowList", "TrendChart", "WeekdayChart", "text_on"]
