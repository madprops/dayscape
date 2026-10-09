"""Search view: runs queries against the store and displays results."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from dayscape.models import SCORE_WORDS, WEEKDAYS_SHORT, format_long
from dayscape.search import parse, search
from dayscape.store import Store
from dayscape.theme import score_color, text_on
from dayscape.widgets.common import Card, icon_button, label


class SearchResultCard(Card):
    daySelected = Signal(object)

    def __init__(self, entry, query, parent: QWidget | None = None):
        super().__init__(parent, margins=16, spacing=8)
        self.entry = entry
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        head = QHBoxLayout()
        title_text = f"{WEEKDAYS_SHORT[entry.day.weekday()]} {format_long(entry.day)}"
        self.title = label(title_text, "h2")
        head.addWidget(self.title)
        head.addStretch(1)

        if entry.score is not None:
            swatch = QWidget()
            swatch.setFixedSize(24, 24)
            c = score_color(entry.score)
            swatch.setStyleSheet(f"background-color: {c.name()}; border-radius: 12px;")
            score_lbl = label(str(entry.score), "h2")
            score_lbl.setStyleSheet(f"color: {text_on(c).name()};")
            score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            slayout = QVBoxLayout(swatch)
            slayout.setContentsMargins(0, 0, 0, 0)
            slayout.addWidget(score_lbl)
            head.addWidget(swatch)

            word_lbl = label(SCORE_WORDS[entry.score], "muted")
            head.addWidget(word_lbl)

        self.body.addLayout(head)

        if entry.notes:
            notes_lbl = label(entry.notes)
            notes_lbl.setWordWrap(True)
            # Highlighting terms could be done here, but simple text for now
            self.body.addWidget(notes_lbl)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.daySelected.emit(self.entry.day)


class SearchView(QWidget):
    daySelected = Signal(object)
    closeRequested = Signal()

    def __init__(self, store: Store, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 32)
        root.setSpacing(18)

        # header
        head = QHBoxLayout()
        head.addWidget(label("Search", "h1"))
        head.addStretch(1)
        close_b = icon_button("×", "Close Search")
        close_b.setStyleSheet("font-size:24px;")
        close_b.clicked.connect(self.closeRequested)
        head.addWidget(close_b)
        root.addLayout(head)

        # search input
        self.input = QLineEdit()
        self.input.setPlaceholderText("Search notes, tags (#work), or scores (score>=8)...")
        self.input.setObjectName("paletteInput")
        self.input.setMinimumHeight(40)
        self.input.textChanged.connect(self._on_search)

        search_container = QWidget()
        search_container.setObjectName("palette")
        s_layout = QVBoxLayout(search_container)
        s_layout.setContentsMargins(12, 4, 12, 4)
        s_layout.addWidget(self.input)
        root.addWidget(search_container)

        self.status = label("", "muted")
        root.addWidget(self.status)

        # results area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(12)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.results_widget)
        root.addWidget(self.scroll, 1)

    def focus_search(self):
        self.input.setFocus()
        self.input.selectAll()

    def set_query(self, query: str):
        self.input.setText(query)

    def _clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_search(self, text: str):
        self._clear_results()
        if not text.strip():
            self.status.setText("Enter a query to search.")
            return

        entries = self.store.all()
        q = parse(text)
        if q.is_empty:
            self.status.setText("Type something to search...")
            return

        results = search(entries, q)
        self.status.setText(f"Found {len(results)} days.")

        for e in results:
            card = SearchResultCard(e, q)
            card.daySelected.connect(self.daySelected)
            self.results_layout.addWidget(card)
