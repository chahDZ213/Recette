"""Dark theme.

A single QSS sheet + Fusion style keeps rendering consistent across
platforms. Colours are defined once in ``PALETTE`` so future themes (light,
high-contrast) only swap this dictionary.
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

PALETTE = {
    "bg": "#1e2227",
    "bg_alt": "#252a31",
    "bg_raised": "#2c323b",
    "border": "#3a4149",
    "text": "#d6dbe1",
    "text_dim": "#8b939e",
    "accent": "#3d8bfd",
    "accent_hover": "#5c9dfd",
    "danger": "#e05561",
    "success": "#57ab5a",
    "warning": "#d29922",
}


def highlight_color(name: str, alpha: int) -> QColor:
    """Semi-transparent overlay colour for hex-view range highlighting."""
    color = QColor(PALETTE[name])
    color.setAlpha(alpha)
    return color


#: Shared highlight roles so every view colours ranges consistently.
HIGHLIGHTS = {
    "diff": lambda: highlight_color("danger", 120),
    "annotation": lambda: highlight_color("accent", 90),
    "bookmark": lambda: highlight_color("success", 90),
    "candidate": lambda: highlight_color("warning", 80),
    "candidate_validated": lambda: highlight_color("success", 120),
}

_QSS = """
QWidget {{
    background-color: {bg};
    color: {text};
    font-size: 13px;
}}
QMainWindow::separator {{
    background: {border};
    width: 3px; height: 3px;
}}
QDockWidget::title {{
    background: {bg_alt};
    padding: 6px 10px;
    border-bottom: 1px solid {border};
}}
QMenuBar {{ background: {bg_alt}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {accent}; color: white; }}
QMenu {{ background: {bg_raised}; border: 1px solid {border}; }}
QToolBar {{ background: {bg_alt}; border: none; spacing: 4px; padding: 3px; }}
QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background: {bg_raised};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: {accent};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {accent}; }}
QPushButton {{
    background: {bg_raised};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 6px 14px;
}}
QPushButton:hover {{ border-color: {accent}; }}
QPushButton:default {{ background: {accent}; color: white; border-color: {accent}; }}
QPushButton:default:hover {{ background: {accent_hover}; }}
QPushButton:disabled {{ color: {text_dim}; }}
QListView, QTreeView, QTableView {{
    background: {bg_alt};
    border: 1px solid {border};
    alternate-background-color: {bg};
}}
QListView::item, QTreeView::item {{ padding: 5px; }}
QListView::item:selected, QTreeView::item:selected, QTableView::item:selected {{
    background: {accent}; color: white;
}}
QHeaderView::section {{
    background: {bg_raised};
    border: none;
    border-right: 1px solid {border};
    border-bottom: 1px solid {border};
    padding: 5px 8px;
}}
QTabWidget::pane {{ border: 1px solid {border}; }}
QTabBar::tab {{
    background: {bg_alt};
    padding: 7px 16px;
    border: 1px solid {border};
    border-bottom: none;
}}
QTabBar::tab:selected {{ background: {bg_raised}; border-bottom: 2px solid {accent}; }}
QStatusBar {{ background: {bg_alt}; border-top: 1px solid {border}; }}
QScrollBar:vertical {{ background: {bg}; width: 12px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {text_dim}; }}
QScrollBar:horizontal {{ background: {bg}; height: 12px; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QToolTip {{ background: {bg_raised}; color: {text}; border: 1px solid {border}; }}
"""


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(_QSS.format(**PALETTE))
