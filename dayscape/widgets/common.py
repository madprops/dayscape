"""Small reusable widgets and QPainter helpers."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dayscape.theme import C, font, score_color, text_on


# ----------------------------------------------------------------- painting
def fill_round(p: QPainter, rect: QRectF, radius: float, color: QColor | str) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(rect, radius, radius)


def stroke_round(
    p: QPainter, rect: QRectF, radius: float, color: QColor | str, width: float = 1.0
) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(color), width))
    half = width / 2
    p.drawRoundedRect(rect.adjusted(half, half, -half, -half), radius, radius)


def score_badge(
    p: QPainter, center: QPointF, diameter: float, value: float | None, decimals: int = 0
) -> None:
    """Solid circular badge with the score inside."""
    if value is None:
        return
    color = score_color(value)
    r = diameter / 2
    rect = QRectF(center.x() - r, center.y() - r, diameter, diameter)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(rect)
    p.setPen(text_on(color))
    p.setFont(font(max(9, int(diameter * (0.42 if decimals else 0.48))), QFont.Weight.Bold))
    txt = f"{value:.{decimals}f}" if decimals else f"{round(value)}"
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, txt)


def score_pill(p: QPainter, rect: QRectF, value: float | None, decimals: int = 1) -> None:
    """Rounded pill showing an average (e.g. week / month)."""
    if value is None:
        fill_round(p, rect, rect.height() / 2, C.EMPTY)
        p.setPen(QColor(C.TEXT_FAINT))
        p.setFont(font(int(rect.height() * 0.5), QFont.Weight.DemiBold))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "–")
        return
    color = score_color(value)
    fill_round(p, rect, rect.height() / 2, color)
    p.setPen(text_on(color))
    p.setFont(font(int(rect.height() * 0.52), QFont.Weight.Bold))
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{value:.{decimals}f}")


def elide(p: QPainter, text: str, width: float) -> str:
    return p.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(width))


def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


# ------------------------------------------------------------------ widgets
def label(text: str = "", name: str | None = None, *, spacing: float = 0.0) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    if spacing:
        f = lbl.font()
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
        lbl.setFont(f)
    return lbl


def caps(text: str) -> QLabel:
    """Small uppercase section label."""
    return label(text.upper(), "faint", spacing=1.2)


def icon_button(glyph: str, tooltip: str) -> QPushButton:
    b = QPushButton(glyph)
    b.setObjectName("iconButton")
    b.setToolTip(tooltip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return b


def divider() -> QFrame:
    f = QFrame()
    f.setObjectName("divider")
    return f


class Segmented(QFrame):
    """Pill-shaped segmented control."""

    changed = Signal(int)

    def __init__(self, labels: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("segment")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, text in enumerate(labels):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.group.addButton(b, i)
            lay.addWidget(b)
        self.group.idClicked.connect(self.changed)
        self.set_index(0)

    def set_index(self, i: int) -> None:
        btn = self.group.button(i)
        if btn:
            btn.setChecked(True)

    def index(self) -> int:
        return self.group.checkedId()

    def set_tooltip(self, i: int, text: str) -> None:
        self.group.button(i).setToolTip(text)


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, margins: int = 18, spacing: int = 12):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(margins, margins, margins, margins)
        self.body.setSpacing(spacing)


class StatTile(Card):
    """Caption / big value / hint, with an optional colour swatch."""

    def __init__(self, caption: str, parent: QWidget | None = None):
        super().__init__(parent, margins=16, spacing=4)
        self.caption = label(caption.upper(), "statLabel", spacing=1.0)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.swatch = QLabel()
        self.swatch.setFixedSize(12, 12)
        self.swatch.hide()
        self.value = label("–", "statValue")
        row.addWidget(self.swatch, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.value)
        row.addStretch(1)
        self.hint = label("", "statHint")
        self.hint.setWordWrap(True)
        self.body.addWidget(self.caption)
        self.body.addLayout(row)
        self.body.addWidget(self.hint)
        self.body.addStretch(1)

    def set(self, value: str, hint: str = "", score: float | None = None) -> None:
        self.value.setText(value)
        self.hint.setText(hint)
        if score is None:
            self.swatch.hide()
        else:
            c = score_color(score).name()
            self.swatch.setStyleSheet(f"background:{c}; border-radius:6px;")
            self.swatch.show()


class Legend(QWidget):
    """Horizontal 1..10 colour legend: 'rough ▢▢▢▢▢▢▢▢▢▢ great'."""

    def __init__(self, parent: QWidget | None = None, cell: int = 12):
        super().__init__(parent)
        self.cell = cell
        self.setFixedHeight(cell + 4)
        self.setMinimumWidth(10 * (cell + 3) + 100)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(font(11))
        p.setPen(QColor(C.TEXT_FAINT))
        fm = p.fontMetrics()
        x = 0.0
        left, right = "Rough", "Great"
        h = self.height()
        p.drawText(QRectF(0, 0, fm.horizontalAdvance(left), h), Qt.AlignmentFlag.AlignVCenter, left)
        x += fm.horizontalAdvance(left) + 8
        for s in range(1, 11):
            fill_round(p, QRectF(x, (h - self.cell) / 2, self.cell, self.cell), 3, score_color(s))
            x += self.cell + 3
        p.setPen(QColor(C.TEXT_FAINT))
        p.drawText(QRectF(x + 5, 0, 60, h), Qt.AlignmentFlag.AlignVCenter, right)
