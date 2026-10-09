"""Main application window and routing."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from dayscape import __version__
from dayscape.db import Database
from dayscape.demo import generate
from dayscape.store import Store
from dayscape.theme import apply, load_fonts
from dayscape.widgets.common import Segmented, label
from dayscape.widgets.editor import DayEditor
from dayscape.widgets.insights_view import InsightsView
from dayscape.widgets.month_view import MonthView
from dayscape.widgets.search_view import SearchView
from dayscape.widgets.week_view import WeekView
from dayscape.widgets.year_view import YearView


def data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", "~")).expanduser() / "Dayscape"
    if sys.platform == "darwin":
        return Path("~/Library/Application Support/Dayscape").expanduser()
    return Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser() / "dayscape"


class MainWindow(QMainWindow):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.setWindowTitle(f"Dayscape {__version__}")
        self.resize(1100, 750)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # Top Bar
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(54)
        tlay = QHBoxLayout(topbar)
        tlay.setContentsMargins(20, 0, 20, 0)

        brand = label("Dayscape", "brand")
        tlay.addWidget(brand)
        tlay.addSpacing(30)

        self.nav = Segmented(["Year", "Month", "Week", "Insights"])
        self.nav.changed.connect(self._nav_changed)
        tlay.addWidget(self.nav)

        tlay.addStretch(1)

        today_btn = label("Today", "muted")
        today_btn.setObjectName("todayButton")
        today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        today_btn.mousePressEvent = lambda e: self._select_day(date.today())
        tlay.addWidget(today_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        tlay.addSpacing(20)

        search_btn = label("Search...    (Ctrl+K)", "muted")
        search_btn.setObjectName("searchButton")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.mousePressEvent = lambda e: self._open_search()
        tlay.addWidget(search_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        main_lay.addWidget(topbar)

        # Splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        main_lay.addWidget(self.splitter, 1)

        # Left Views (Stack)
        self.stack = QStackedWidget()
        self.stack.setObjectName("viewStack")

        self.year_view = YearView(store)
        self.year_view.daySelected.connect(self._select_day)
        self.year_view.weekClicked.connect(self._jump_to_week)
        self.year_view.monthClicked.connect(self._jump_to_month)

        self.month_view = MonthView(store)
        self.month_view.daySelected.connect(self._select_day)
        self.month_view.dayActivated.connect(self._activate_day)
        self.month_view.weekClicked.connect(self._jump_to_week)

        self.week_view = WeekView(store)
        self.week_view.daySelected.connect(self._select_day)
        self.week_view.dayActivated.connect(self._activate_day)

        self.insights_view = InsightsView(store)
        self.insights_view.daySelected.connect(self._select_day)
        self.insights_view.searchRequested.connect(self._run_search)

        self.search_view = SearchView(store)
        self.search_view.daySelected.connect(self._select_day)
        self.search_view.closeRequested.connect(self._close_search)

        self.stack.addWidget(self.year_view)  # 0
        self.stack.addWidget(self.month_view)  # 1
        self.stack.addWidget(self.week_view)  # 2
        self.stack.addWidget(self.insights_view)  # 3
        self.stack.addWidget(self.search_view)  # 4

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.stack)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.splitter.addWidget(scroll)

        # Right Editor
        self.editor = DayEditor(store)
        self.editor.dateRequested.connect(self._select_day)
        self.splitter.addWidget(self.editor)

        self.splitter.setSizes([700, 400])

        settings = QSettings()
        splitter_state = settings.value("splitterState")
        if splitter_state:
            self.splitter.restoreState(splitter_state)

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+K"), self, self._open_search)
        QShortcut(QKeySequence("Ctrl+F"), self, self._open_search)
        QShortcut(QKeySequence("Escape"), self, self._close_search_if_open)

        # Initialize
        self.current_nav_index = 0
        self._select_day(date.today())

    def _nav_changed(self, idx: int):
        self.current_nav_index = idx
        if self.stack.currentIndex() != 4:  # not search
            self.stack.setCurrentIndex(idx)
        else:
            self.stack.setCurrentIndex(idx)

    def _select_day(self, d: date):
        self.editor.set_date(d)
        self.year_view.set_selected(d)
        self.month_view.set_selected(d)
        self.week_view.set_selected(d)

    def _activate_day(self, d: date):
        self._select_day(d)
        self.editor.focus_notes()

    def _jump_to_week(self, monday: date):
        self._select_day(monday)
        self.nav.set_index(2)

    def _jump_to_month(self, year: int, month: int):
        self._select_day(date(year, month, 1))
        self.nav.set_index(1)

    def _open_search(self):
        self.stack.setCurrentIndex(4)
        self.search_view.focus_search()

    def _run_search(self, query: str):
        self._open_search()
        self.search_view.set_query(query)

    def _close_search(self):
        self.stack.setCurrentIndex(self.current_nav_index)

    def _close_search_if_open(self):
        if self.stack.currentIndex() == 4:
            self._close_search()

    def closeEvent(self, e):
        self.editor.flush()
        settings = QSettings()
        settings.setValue("splitterState", self.splitter.saveState())
        super().closeEvent(e)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dayscape vibe journal.")
    parser.add_argument(
        "--demo", action="store_true", help="Generate sample data and run in-memory."
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setOrganizationName("Dayscape")
    app.setApplicationName("Dayscape")
    app.setDesktopFileName("dayscape.desktop")

    icon_path = Path(__file__).parent / "assets" / "dayscape.svg"
    app.setWindowIcon(QIcon(str(icon_path)))

    font_dir = os.environ.get("DAYSCAPE_FONT_DIR")
    load_fonts(font_dir)
    apply(app)

    if args.demo:
        db = Database(":memory:")
        store = Store(db)
        store.db.bulk_save(generate(seed=42))
    else:
        path = data_dir() / "dayscape.db"
        db = Database(path)
        store = Store(db)

    window = MainWindow(store)
    window.show()

    return app.exec()
