"""Right-hand panel: rate and write about the selected day. Saves automatically."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, QRegularExpression, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from dayscape import stats
from dayscape.models import SCORE_WORDS, WEEKDAYS, format_long, relative_label
from dayscape.store import Store
from dayscape.theme import C, font, mix, score_color, text_on
from dayscape.widgets.common import caps, divider, fill_round, icon_button, label, stroke_round


class ScorePicker(QWidget):
    """Ten colour-coded segments; click to rate, click again to clear."""

    scoreChanged = Signal(object)  # int | None

    GAP = 5

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._score: int | None = None
        self._hover: int | None = None
        self.setMouseTracking(True)
        self.setFixedHeight(40)
        self.setMinimumWidth(10 * 22 + 9 * self.GAP)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def score(self) -> int | None:
        return self._score

    def set_score(self, value: int | None, emit: bool = False) -> None:
        if value == self._score:
            return
        self._score = value
        self.update()
        if emit:
            self.scoreChanged.emit(value)

    def _cell_rect(self, i: int) -> QRectF:
        w = (self.width() - 9 * self.GAP) / 10
        return QRectF((i - 1) * (w + self.GAP), 0, w, self.height())

    def _hit(self, x: float) -> int | None:
        for i in range(1, 11):
            r = self._cell_rect(i)
            if r.left() - self.GAP / 2 <= x <= r.right() + self.GAP / 2:
                return i
        return None

    def mouseMoveEvent(self, e):
        h = self._hit(e.position().x())
        if h != self._hover:
            self._hover = h
            if h:
                self.setToolTip(f"{h} · {SCORE_WORDS[h]}")
            self.update()

    def leaveEvent(self, _):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        h = self._hit(e.position().x())
        if h is not None:
            self.set_score(None if h == self._score else h, emit=True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i in range(1, 11):
            r = self._cell_rect(i)
            col = score_color(i)
            selected = i == self._score
            hovered = i == self._hover
            if selected:
                fill_round(p, r, 9, col)
                p.setPen(text_on(col))
                p.setFont(font(15, QFont.Weight.Bold))
            else:
                bg = mix(C.BG, col, 0.30 if hovered else 0.12)
                fill_round(p, r, 9, bg)
                if hovered:
                    stroke_round(p, r, 9, mix(C.BG, col, 0.8), 1.2)
                p.setPen(mix(C.TEXT_FAINT, col, 0.85 if hovered else 0.55))
                p.setFont(font(14, QFont.Weight.DemiBold))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(i))
        p.end()


class TagHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self.tag_fmt = QTextCharFormat()
        self.tag_fmt.setForeground(QColor(C.ACCENT_GLOW))
        self.tag_fmt.setFontWeight(QFont.Weight.DemiBold)
        self.bullet_fmt = QTextCharFormat()
        self.bullet_fmt.setForeground(QColor(C.TEXT_FAINT))
        self.tag_re = QRegularExpression(r"#[\w\-]+")
        self.bullet_re = QRegularExpression(r"^\s*[-*•·]")

    def highlightBlock(self, text: str) -> None:
        m = self.bullet_re.match(text)
        if m.hasMatch():
            self.setFormat(m.capturedStart(), m.capturedLength(), self.bullet_fmt)
        it = self.tag_re.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), self.tag_fmt)


class NotesEdit(QPlainTextEdit):
    """Plain text, no spell-check, auto-continues '- ' bullet lists."""

    escaped = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("notes")
        self.setTabChangesFocus(True)
        self.setPlaceholderText("- what happened\n- how it felt\n- #tags group themes")
        # No predictive text / auto-capitalisation from input methods.
        self.setInputMethodHints(
            Qt.InputMethodHint.ImhNoPredictiveText
            | Qt.InputMethodHint.ImhNoAutoUppercase
            | Qt.InputMethodHint.ImhSensitiveData
        )
        self.document().setDocumentMargin(4)
        self.setFont(font(20))
        self.setCursorWidth(2)
        self.highlighter = TagHighlighter(self.document())

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.escaped.emit()
            return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            e.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            cur = self.textCursor()
            line = cur.block().text()
            stripped = line.lstrip()
            for marker in ("- ", "• ", "* "):
                if stripped.startswith(marker):
                    indent = line[: len(line) - len(stripped)]
                    if stripped.strip() in (marker.strip(),):
                        # Empty bullet: end the list instead of adding another.
                        cur.select(QTextCursor.SelectionType.BlockUnderCursor)
                        cur.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                        cur.movePosition(
                            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
                        )
                        cur.removeSelectedText()
                        return
                    cur.insertText("\n" + indent + marker)
                    self.ensureCursorVisible()
                    return
        super().keyPressEvent(e)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        if not self.toPlainText():
            self.setPlainText("- ")
            self.moveCursor(QTextCursor.MoveOperation.End)

    def focusOutEvent(self, e):
        if self.toPlainText().strip() in ("-", "•", "*"):
            self.clear()
        super().focusOutEvent(e)


class WeekdayStrip(QWidget):
    """The last N same-weekdays as small coloured tiles; click to jump."""

    dateClicked = Signal(object)

    N = 10

    def __init__(self, store: Store, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self.day: date | None = None
        self.setFixedHeight(34)
        self.setMouseTracking(True)
        self._rects: list[tuple[QRectF, date]] = []

    def set_day(self, d: date) -> None:
        self.day = d
        self.update()

    def days(self) -> list[date]:
        if not self.day:
            return []
        return [self.day - timedelta(weeks=k) for k in range(self.N - 1, -1, -1)]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._rects.clear()
        days = self.days()
        gap = 5
        w = (self.width() - gap * (self.N - 1)) / self.N
        for i, d in enumerate(days):
            r = QRectF(i * (w + gap), 2, w, self.height() - 4)
            s = self.store.score(d)
            current = d == self.day
            fill_round(p, r, 7, score_color(s) if s else C.EMPTY)
            if current:
                stroke_round(p, r.adjusted(-2, -2, 2, 2), 9, C.TEXT, 1.5)
            if s:
                p.setPen(text_on(score_color(s)))
                p.setFont(font(12, QFont.Weight.Bold))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(s))
            self._rects.append((r, d))
        p.end()

    def mouseMoveEvent(self, e):
        for r, d in self._rects:
            if r.contains(e.position()):
                s = self.store.score(d)
                self.setToolTip(f"{format_long(d)} — {s if s else 'not rated'}")
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                return
        self.setToolTip("")

    def mousePressEvent(self, e):
        for r, d in self._rects:
            if r.contains(e.position()):
                self.dateClicked.emit(d)
                return


class DayEditor(QWidget):
    dateRequested = Signal(object)
    focusReleased = Signal()

    def __init__(self, store: Store, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self.day: date = date.today()
        self._loading = False
        self.setObjectName("editorPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(280)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(450)
        self._timer.timeout.connect(self.flush)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(0)

        # header -------------------------------------------------------------
        nav = QHBoxLayout()
        nav.setSpacing(4)
        self.weekday = caps("")
        self.relative = label("", "muted")
        self.relative.setStyleSheet(f"color:{C.ACCENT_GLOW}; font-size:12px; font-weight:600;")
        prev_b = icon_button("‹", "Previous day  (Alt+←)")
        next_b = icon_button("›", "Next day  (Alt+→)")
        prev_b.setStyleSheet("font-size:20px;")
        next_b.setStyleSheet("font-size:20px;")
        prev_b.clicked.connect(lambda: self.dateRequested.emit(self.day - timedelta(days=1)))
        next_b.clicked.connect(lambda: self.dateRequested.emit(self.day + timedelta(days=1)))
        nav.addWidget(self.weekday)
        nav.addSpacing(8)
        nav.addWidget(self.relative)
        nav.addStretch(1)
        nav.addWidget(prev_b)
        nav.addWidget(next_b)
        root.addLayout(nav)
        root.addSpacing(4)
        self.title = label("", "h1")
        root.addWidget(self.title)
        root.addSpacing(20)

        # score --------------------------------------------------------------
        srow = QHBoxLayout()
        srow.addWidget(caps("Vibe"))
        srow.addStretch(1)
        self.score_word = label("", "muted")
        self.score_word.setFont(font(13, QFont.Weight.DemiBold))
        srow.addWidget(self.score_word)
        root.addLayout(srow)
        root.addSpacing(10)
        self.picker = ScorePicker()
        self.picker.scoreChanged.connect(self._on_score)
        root.addWidget(self.picker)
        root.addSpacing(22)

        # notes --------------------------------------------------------------
        nrow = QHBoxLayout()
        nrow.addWidget(caps("Notes"))
        nrow.addStretch(1)
        self.save_state = label("", "saveState")
        nrow.addWidget(self.save_state)
        root.addLayout(nrow)
        root.addSpacing(10)
        self.notes = NotesEdit()
        self.notes.textChanged.connect(self._on_text)
        self.notes.escaped.connect(self.focusReleased)
        root.addWidget(self.notes, 1)
        root.addSpacing(8)
        hint = label("One thing per line · #tags become themes in Insights", "saveState")
        root.addWidget(hint)
        root.addSpacing(22)
        root.addWidget(divider())
        root.addSpacing(16)

        # same weekday context -----------------------------------------------
        crow = QHBoxLayout()
        self.ctx_title = caps("")
        self.ctx_avg = label("", "muted")
        crow.addWidget(self.ctx_title)
        crow.addStretch(1)
        crow.addWidget(self.ctx_avg)
        root.addLayout(crow)
        root.addSpacing(10)
        self.strip = WeekdayStrip(store)
        self.strip.dateClicked.connect(self.dateRequested)
        root.addWidget(self.strip)

        store.changed.connect(self._on_store_changed)

    # ---------------------------------------------------------------- public
    def set_date(self, d: date) -> None:
        if self._timer.isActive():
            self.flush()
        self.day = d
        self._load()

    def set_score(self, s: int | None) -> None:
        self.picker.set_score(s, emit=True)

    def focus_notes(self) -> None:
        self.notes.setFocus()
        self.notes.moveCursor(QTextCursor.MoveOperation.End)

    def flush(self) -> None:
        self._timer.stop()
        if self._loading:
            return
        text = self.notes.toPlainText()
        if text.strip() in ("-", "•", "*"):
            text = ""
        if self.store.save(self.day, self.picker.score(), text):
            self.save_state.setText("Saved ✓")
            QTimer.singleShot(1600, lambda: self.save_state.setText(""))
        elif self.save_state.text() == "Saving…":
            self.save_state.setText("")

    # --------------------------------------------------------------- private
    def _load(self) -> None:
        self._loading = True
        e = self.store.get(self.day)
        self.weekday.setText(WEEKDAYS[self.day.weekday()].upper())
        self.relative.setText(relative_label(self.day))
        self.title.setText(format_long(self.day))
        self.picker.set_score(e.score if e else None)
        text = e.notes if e else ""
        if self.notes.toPlainText() != text:
            self.notes.setPlainText(text)
        self.save_state.setText("")
        self._update_score_word()
        self._update_context()
        self._loading = False

    def _on_score(self, _):
        self._update_score_word()
        if not self._loading:
            self.flush()

    def _on_text(self):
        if self._loading:
            return
        self.save_state.setText("Saving…")
        self._timer.start()

    def _on_store_changed(self, d):
        if (
            (d is None or d == self.day)
            and not self._timer.isActive()
            and not self.notes.hasFocus()
        ):
            self._load()
        self._update_context()

    def _update_score_word(self) -> None:
        s = self.picker.score()
        if s is None:
            self.score_word.setText("Not rated")
            self.score_word.setStyleSheet(f"color:{C.TEXT_FAINT};")
        else:
            self.score_word.setText(f"{s} · {SCORE_WORDS[s]}")
            self.score_word.setStyleSheet(f"color:{score_color(s).name()};")

    def _update_context(self) -> None:
        wd = self.day.weekday()
        name = WEEKDAYS[wd]
        self.ctx_title.setText(f"LAST {WeekdayStrip.N} {name.upper()}S")
        summary = stats.by_weekday(self.store.all())[wd]
        if summary.mean is None:
            self.ctx_avg.setText("")
        else:
            c = score_color(summary.mean).name()
            self.ctx_avg.setText(
                f"<span style='color:{C.TEXT_FAINT}'>{name}s avg</span> "
                f"<b style='color:{c}'>{summary.mean:.1f}</b>"
            )
        self.strip.set_day(self.day)


__all__ = ["DayEditor", "NotesEdit", "QPointF", "ScorePicker"]
