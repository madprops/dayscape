"""Design system: palette, score colour scale, fonts and the global stylesheet."""

from __future__ import annotations

import itertools
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication


class C:
    BG = "#0C0E13"
    SURFACE = "#12151C"
    SURFACE_2 = "#181C25"
    ELEVATED = "#1F2430"
    EMPTY = "#191D27"
    BORDER = "#242937"
    BORDER_STRONG = "#333A4B"
    TEXT = "#E8EAF1"
    TEXT_DIM = "#A1A8B9"
    TEXT_FAINT = "#646B7F"
    ACCENT = "#9381FF"
    ACCENT_SOFT = "#2B2652"
    ACCENT_GLOW = "#B7AAFF"


# A perceptually-smooth diverging scale: crimson → coral → amber → lime → jade → teal.
SCORE_STOPS: list[tuple[float, str]] = [
    (1, "#C93752"),
    (2, "#DE4B4F"),
    (3, "#EA6A48"),
    (4, "#F08F45"),
    (5, "#F2B44C"),
    (6, "#D9C757"),
    (7, "#A6D063"),
    (8, "#6CC67C"),
    (9, "#3DBC93"),
    (10, "#26B0B0"),
]
_STOPS = [(v, QColor(h)) for v, h in SCORE_STOPS]


def qc(hex_or_color: str | QColor, alpha: int | None = None) -> QColor:
    c = QColor(hex_or_color)
    if alpha is not None:
        c.setAlpha(alpha)
    return c


def mix(a: QColor | str, b: QColor | str, t: float) -> QColor:
    a, b = QColor(a), QColor(b)
    t = max(0.0, min(1.0, t))
    return QColor.fromRgbF(
        a.redF() + (b.redF() - a.redF()) * t,
        a.greenF() + (b.greenF() - a.greenF()) * t,
        a.blueF() + (b.blueF() - a.blueF()) * t,
        a.alphaF() + (b.alphaF() - a.alphaF()) * t,
    )


def score_color(value: float | None) -> QColor:
    """Colour for a score; fractional values (averages) are interpolated."""
    if value is None:
        return QColor(C.EMPTY)
    value = max(1.0, min(10.0, float(value)))
    for (v0, c0), (v1, c1) in itertools.pairwise(_STOPS):
        if value <= v1:
            return mix(c0, c1, (value - v0) / (v1 - v0))
    return QColor(_STOPS[-1][1])


def tint(value: float | None, strength: float = 0.18, base: str = C.SURFACE_2) -> QColor:
    """Score colour washed into a dark surface — used for large card backgrounds."""
    if value is None:
        return QColor(base)
    return mix(base, score_color(value), strength)


def text_on(color: QColor) -> QColor:
    lum = 0.2126 * color.redF() + 0.7152 * color.greenF() + 0.0722 * color.blueF()
    return QColor("#0C0E13") if lum > 0.42 else QColor("#FFFFFF")


# ------------------------------------------------------------------ fonts
UI_FAMILY = "Inter"


def load_fonts(font_dir: str | None) -> None:
    """Register bundled fonts (Inter from nixpkgs) and pick the UI family."""
    global UI_FAMILY
    families: list[str] = []
    if font_dir and Path(font_dir).is_dir():
        for f in sorted(Path(font_dir).rglob("*")):
            if f.suffix.lower() in (".ttf", ".otf", ".ttc"):
                fid = QFontDatabase.addApplicationFont(str(f))
                if fid >= 0:
                    families += QFontDatabase.applicationFontFamilies(fid)
    available = set(QFontDatabase.families()) | set(families)
    for cand in (
        "Inter",
        "Inter Variable",
        "Inter Display",
        "Noto Sans",
        "Cantarell",
        "DejaVu Sans",
    ):
        if cand in available:
            UI_FAMILY = cand
            break


def font(px: int, weight: QFont.Weight = QFont.Weight.Normal, spacing: float = 0.0) -> QFont:
    f = QFont(UI_FAMILY)
    f.setPixelSize(px)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


# -------------------------------------------------------------- stylesheet
STYLESHEET = f"""
* {{ outline: none; }}
QWidget {{ color: {C.TEXT}; font-size: 13px; }}
QMainWindow, #central, #viewStack, #viewStack > QWidget {{ background: {C.BG}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}

/* top bar */
#topbar {{ background: {C.SURFACE}; border-bottom: 1px solid {C.BORDER}; }}
#brand {{ font-size: 15px; font-weight: 600; }}
#brandSub {{ color: {C.TEXT_FAINT}; font-size: 12px; }}

QPushButton {{
    background: transparent; color: {C.TEXT_DIM};
    border: 1px solid {C.BORDER}; border-radius: 8px; padding: 6px 12px;
}}
QPushButton:hover {{ background: {C.SURFACE_2}; color: {C.TEXT}; border-color: {C.BORDER_STRONG}; }}
QPushButton:pressed {{ background: {C.ELEVATED}; }}
QPushButton:focus {{ border-color: {C.ACCENT}; }}

#segment {{ background: {C.BG}; border: 1px solid {C.BORDER}; border-radius: 10px; }}
#segment QPushButton {{ border: none; border-radius: 7px; padding: 6px 16px; font-weight: 500; }}
#segment QPushButton:hover {{ background: {C.SURFACE_2}; }}
#segment QPushButton:checked {{ background: {C.ELEVATED}; color: {C.TEXT}; }}

#searchButton {{
    background: {C.BG}; text-align: left; padding: 7px 12px; min-width: 250px;
    color: {C.TEXT_FAINT};
}}
#searchButton:hover {{ color: {C.TEXT_DIM}; border-color: {C.ACCENT}; background: {C.BG}; }}

#iconButton {{
    border: none; border-radius: 7px; padding: 0px;
    min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;
    font-size: 15px; color: {C.TEXT_DIM};
}}
#iconButton:hover {{ background: {C.ELEVATED}; color: {C.TEXT}; }}

#primaryButton {{ background: {C.ACCENT_SOFT}; color: {C.ACCENT_GLOW}; border-color: #3B3470; }}
#primaryButton:hover {{ background: #352E66; color: #FFFFFF; border-color: {C.ACCENT}; }}

/* headings */
#h1 {{ font-size: 28px; font-weight: 600; }}
#h2 {{ font-size: 16px; font-weight: 600; }}
#muted {{ color: {C.TEXT_DIM}; }}
#faint {{ color: {C.TEXT_FAINT}; font-size: 11px; font-weight: 600; }}
#statValue {{ font-size: 22px; font-weight: 600; }}
#statLabel {{ color: {C.TEXT_FAINT}; font-size: 11px; font-weight: 600; }}
#statHint {{ color: {C.TEXT_DIM}; font-size: 12px; }}

/* cards & panels */
#card {{ background: {C.SURFACE}; border: 1px solid {C.BORDER}; border-radius: 14px; }}
#editorPanel {{ background: {C.SURFACE}; border-left: 1px solid {C.BORDER}; }}
#divider {{ background: {C.BORDER}; max-height: 1px; min-height: 1px; }}

QPlainTextEdit#notes {{
    background: {C.BG}; border: 1px solid {C.BORDER}; border-radius: 12px;
    padding: 10px 8px; font-size: 14px;
    selection-background-color: {C.ACCENT_SOFT}; selection-color: {C.TEXT};
}}
QPlainTextEdit#notes:focus {{ border-color: #4A4290; }}

#saveState {{ color: {C.TEXT_FAINT}; font-size: 12px; }}

/* splitter */
QSplitter::handle {{ background: {C.BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}

/* scrollbars */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle {{ background: {C.BORDER_STRONG}; border-radius: 3px; }}
QScrollBar::handle:vertical {{ min-height: 32px; }}
QScrollBar::handle:horizontal {{ min-width: 32px; }}
QScrollBar::handle:hover {{ background: #454D62; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QToolTip {{
    background: {C.ELEVATED}; color: {C.TEXT}; border: 1px solid {C.BORDER_STRONG};
    padding: 8px 10px; border-radius: 8px;
}}
QMenu {{
    background: {C.ELEVATED}; border: 1px solid {C.BORDER_STRONG};
    border-radius: 10px; padding: 6px;
}}
QMenu::item {{ padding: 7px 26px 7px 14px; border-radius: 6px; color: {C.TEXT}; }}
QMenu::item:selected {{ background: {C.ACCENT_SOFT}; }}
QMenu::separator {{ height: 1px; background: {C.BORDER}; margin: 5px 8px; }}

/* command palette */
#palette {{ background: {C.SURFACE_2}; border: 1px solid {C.BORDER_STRONG}; border-radius: 16px; }}
QLineEdit#paletteInput {{
    background: transparent; border: none; font-size: 18px; padding: 4px 2px;
    selection-background-color: {C.ACCENT_SOFT};
}}
QListView#paletteList {{ background: transparent; border: none; }}
#paletteFooter {{ color: {C.TEXT_FAINT}; font-size: 12px; }}
#kbd {{
    color: {C.TEXT_DIM}; background: {C.ELEVATED}; border: 1px solid {C.BORDER_STRONG};
    border-radius: 5px; padding: 1px 6px; font-size: 11px;
}}

QDialog, QMessageBox {{ background: {C.SURFACE}; }}
QLabel {{ background: transparent; }}
"""


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: C.BG,
        QPalette.ColorRole.WindowText: C.TEXT,
        QPalette.ColorRole.Base: C.SURFACE,
        QPalette.ColorRole.AlternateBase: C.SURFACE_2,
        QPalette.ColorRole.Text: C.TEXT,
        QPalette.ColorRole.Button: C.SURFACE_2,
        QPalette.ColorRole.ButtonText: C.TEXT,
        QPalette.ColorRole.Highlight: C.ACCENT_SOFT,
        QPalette.ColorRole.HighlightedText: C.TEXT,
        QPalette.ColorRole.ToolTipBase: C.ELEVATED,
        QPalette.ColorRole.ToolTipText: C.TEXT,
        QPalette.ColorRole.PlaceholderText: C.TEXT_FAINT,
        QPalette.ColorRole.Link: C.ACCENT,
        QPalette.ColorRole.Mid: C.BORDER,
        QPalette.ColorRole.Dark: C.BG,
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(C.TEXT_FAINT))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(C.TEXT_FAINT))
    app.setPalette(pal)
    app.setFont(font(13))
    app.setStyleSheet(STYLESHEET)
