"""
ui/theme.py

Shared UI theme constants and stylesheet helpers for OutpostX.

Purpose
-------
Provide a single place for application-wide visual styling so that
main windows, dialogs, toolbars, menu bars, grouped panels, trees,
and tables all share a consistent appearance.

Design goals
------------
- Calm, readable, low-fatigue visual presentation
- Subtle grouping and emphasis, suitable for long-running operational use
- Easy to adjust centrally as the application evolves
- Avoid over-styled or flashy UI choices

Usage
-----
Import the constants or helper functions you need:

    from ui.theme import (
        MENU_BAR_STYLE,
        GROUP_BOX_STYLE,
        DIALOG_STYLE,
        MAIN_WINDOW_STYLE,
        TREE_STYLE,
        TABLE_STYLE,
        toolbar_style,
    )

Examples
--------
    self.setStyleSheet(MAIN_WINDOW_STYLE)

    self.menuBar().setStyleSheet(MENU_BAR_STYLE)

    tb = self.addToolBar("Main")
    tb.setObjectName("MainToolbar")
    tb.setStyleSheet(toolbar_style("MainToolbar"))

    group.setStyleSheet(GROUP_BOX_STYLE)

    self.folderTree.setAlternatingRowColors(True)
    self.folderTree.setStyleSheet(TREE_STYLE)

    self.msgTable.setAlternatingRowColors(True)
    self.msgTable.setStyleSheet(TABLE_STYLE)

Notes
-----
- Many styles are object-name aware. For example, toolbar_style()
  targets a specific QToolBar object name.
- This is a first-pass theme module. It can later be extended with
  more specialized button, status bar, splitter, message state, or
  accessibility styles if needed.
"""

from __future__ import annotations


# ----------------------------------------------------------------------
# Core color constants
# ----------------------------------------------------------------------

WHITE = "#ffffff"
BLACK = "#000000"

MENU_BAR_BG = "#dfe8f6"
TOOLBAR_BG = "#eef3fb"
WINDOW_BG = "#f8f9fa"
DIALOG_BG = "#f8f9fa"
PANEL_BG = "#f4f6f8"

HOVER_BG = "#dbe7f8"
PRESSED_BG = "#cbdcf5"
SELECT_BG = "#cfe0f7"

BORDER = "#a0a0a0"
LIGHT_BORDER = "#c7c7c7"
BUTTON_BORDER_HOVER = "#b7c9e6"

TEXT = "#202020"
MUTED_TEXT = "#505050"
DISABLED_TEXT = "#808080"


# ----------------------------------------------------------------------
# Menu bar style
# ----------------------------------------------------------------------

MENU_BAR_STYLE = f"""
QMenuBar {{
    background-color: {MENU_BAR_BG};
    color: {TEXT};
    border-bottom: 1px solid {BORDER};
}}

QMenu::item:disabled {{
    color: {DISABLED_TEXT};
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 4px 10px;
    margin: 2px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {HOVER_BG};
}}

QMenuBar::item:pressed {{
    background-color: {PRESSED_BG};
}}

QMenu {{
    background-color: {WHITE};
    color: {TEXT};
    border: 1px solid {BORDER};
}}

QMenu::item {{
    padding: 6px 24px 6px 24px;
}}

QMenu::item:selected {{
    background-color: {SELECT_BG};
}}

QMenu::separator {{
    height: 1px;
    background: {LIGHT_BORDER};
    margin: 4px 8px 4px 8px;
}}
"""


# ----------------------------------------------------------------------
# Toolbar style helper
# ----------------------------------------------------------------------

def toolbar_style(object_name: str) -> str:
    """
    Return a stylesheet for a toolbar with the given object name.

    Parameters
    ----------
    object_name : str
        The toolbar's Qt object name, for example "MainToolbar".

    Returns
    -------
    str
        A Qt stylesheet string scoped to the named toolbar.
    """
    return f"""
QToolBar#{object_name} {{
    background-color: {TOOLBAR_BG};
    color: {TEXT};
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 4px;
}}

QToolBar#{object_name} QToolButton:disabled {{
    color: {DISABLED_TEXT};
    background-color: transparent;
    border: 1px solid transparent;
}}

QToolBar#{object_name}::separator {{
    background: {LIGHT_BORDER};
    width: 1px;
    margin: 4px 6px 4px 6px;
}}

QToolBar#{object_name} QToolButton {{
    background-color: transparent;
    color: {TEXT};
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    margin: 1px;
}}

QToolBar#{object_name} QToolButton:hover {{
    background-color: {HOVER_BG};
    border: 1px solid {BUTTON_BORDER_HOVER};
}}

QToolBar#{object_name} QToolButton:pressed {{
    background-color: {PRESSED_BG};
}}

QToolBar#{object_name} QLabel {{
    background: transparent;
    color: {TEXT};
    padding-left: 4px;
    padding-right: 2px;
}}

QToolBar#{object_name} QComboBox {{
    background-color: {WHITE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 2px 8px 2px 8px;
    min-width: 120px;
}}

QToolBar#{object_name} QComboBox::drop-down {{
    border: none;
}}

QToolBar#{object_name} QComboBox QAbstractItemView {{
    background-color: {WHITE};
    color: {TEXT};
    selection-background-color: {SELECT_BG};
    border: 1px solid {BORDER};
}}
"""


# ----------------------------------------------------------------------
# Group box style
# ----------------------------------------------------------------------

GROUP_BOX_STYLE = f"""
QGroupBox {{
    background-color: {PANEL_BG};
    color: {TEXT};
    border: 1px solid {LIGHT_BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding: 8px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px 0 4px;
    color: {TEXT};
    background-color: transparent;
}}
"""


# ----------------------------------------------------------------------
# Dialog / general form style
# ----------------------------------------------------------------------

DIALOG_STYLE = f"""
QDialog {{
    background-color: {DIALOG_BG};
    color: {TEXT};
}}

QWidget {{
    color: {TEXT};
}}

QLabel {{
    color: {TEXT};
    background: transparent;
}}

QLineEdit,
QPlainTextEdit,
QTextEdit,
QSpinBox,
QDoubleSpinBox,
QDateEdit,
QTimeEdit,
QDateTimeEdit,
QComboBox,
QListWidget,
QTreeWidget,
QTreeView,
QTableWidget,
QTableView {{
    background-color: {WHITE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px;
}}

QLineEdit:focus,
QPlainTextEdit:focus,
QTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QDateEdit:focus,
QTimeEdit:focus,
QDateTimeEdit:focus,
QComboBox:focus,
QListWidget:focus,
QTreeWidget:focus,
QTreeView:focus,
QTableWidget:focus,
QTableView:focus {{
    border: 1px solid {BUTTON_BORDER_HOVER};
}}

QPushButton {{
    background-color: {WHITE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 12px;
    min-height: 22px;
}}

QPushButton:hover {{
    background-color: {HOVER_BG};
    border: 1px solid {BUTTON_BORDER_HOVER};
}}

QPushButton:pressed {{
    background-color: {PRESSED_BG};
}}

QPushButton:disabled,
QLineEdit:disabled,
QPlainTextEdit:disabled,
QTextEdit:disabled,
QComboBox:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled {{
    color: {DISABLED_TEXT};
}}

QCheckBox,
QRadioButton {{
    color: {TEXT};
    spacing: 6px;
}}

QTabWidget::pane {{
    border: 1px solid {LIGHT_BORDER};
    background: {WHITE};
}}

QTabBar::tab {{
    background: {PANEL_BG};
    color: {TEXT};
    border: 1px solid {LIGHT_BORDER};
    padding: 6px 12px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}

QTabBar::tab:selected {{
    background: {WHITE};
}}

QTabBar::tab:hover {{
    background: {HOVER_BG};
}}
"""

# ------------------------------------------------------------
# Transcript Window Style
# ------------------------------------------------------------
TRANSCRIPT_STYLE = """
QPlainTextEdit {
    background-color: #f8f8f8;
    color: #202020;
    font-family: Menlo, Consolas, "Courier New", monospace;
    font-size: 10pt;
    selection-background-color: #bcdcff;
}
"""

# ----------------------------------------------------------------------
# Main window / generic widget style
# ----------------------------------------------------------------------

MAIN_WINDOW_STYLE = f"""
QMainWindow {{
    background-color: {WINDOW_BG};
    color: {TEXT};
}}

QWidget {{
    color: {TEXT};
}}

QStatusBar {{
    background-color: {PANEL_BG};
    color: {TEXT};
    border-top: 1px solid {LIGHT_BORDER};
}}
"""


# ----------------------------------------------------------------------
# Tree view / tree widget style
# ----------------------------------------------------------------------

TREE_STYLE = f"""
QTreeWidget,
QTreeView {{
    background-color: {WHITE};
    alternate-background-color: {PANEL_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    show-decoration-selected: 1;
}}

QTreeWidget::item,
QTreeView::item {{
    padding: 4px 2px 4px 2px;
}}

QTreeWidget::item:selected,
QTreeView::item:selected {{
    background-color: {SELECT_BG};
    color: {TEXT};
}}

QTreeWidget::item:hover,
QTreeView::item:hover {{
    background-color: {HOVER_BG};
}}

QHeaderView::section {{
    background-color: {PANEL_BG};
    color: {TEXT};
    border: 1px solid {LIGHT_BORDER};
    padding: 4px 6px;
}}
"""


# ----------------------------------------------------------------------
# Table view / table widget style
# ----------------------------------------------------------------------

TABLE_STYLE = f"""
QTableWidget,
QTableView {{
    background-color: {WHITE};
    alternate-background-color: {PANEL_BG};
    color: {TEXT};
    gridline-color: {LIGHT_BORDER};
    border: 1px solid {BORDER};
    border-radius: 4px;
    selection-background-color: {SELECT_BG};
    selection-color: {TEXT};
}}

QTableWidget::item,
QTableView::item {{
    padding: 4px;
}}

QTableWidget::item:selected,
QTableView::item:selected {{
    background-color: {SELECT_BG};
    color: {TEXT};
}}

QTableWidget::item:hover,
QTableView::item:hover {{
    background-color: {HOVER_BG};
}}

QHeaderView::section {{
    background-color: {PANEL_BG};
    color: {TEXT};
    border: 1px solid {LIGHT_BORDER};
    padding: 4px 6px;
}}

QTableCornerButton::section {{
    background-color: {PANEL_BG};
    border: 1px solid {LIGHT_BORDER};
}}
"""

# ----------------------------------------------------------------------
# Splitter style
# ----------------------------------------------------------------------

SPLITTER_STYLE = f"""
QSplitter {{
    background-color: transparent;
}}

QSplitter::handle {{
    background-color: {LIGHT_BORDER};
}}

QSplitter::handle:horizontal {{
    width: 6px;
    margin: 2px 0px 2px 0px;
    border-radius: 2px;
}}

QSplitter::handle:vertical {{
    height: 6px;
    margin: 0px 2px 0px 2px;
    border-radius: 2px;
}}

QSplitter::handle:hover {{
    background-color: {HOVER_BG};
}}

QSplitter::handle:pressed {{
    background-color: {PRESSED_BG};
}}
"""

# ----------------------------------------------------------------------
# Primary toolbutton style (e.g., Send/Receive)
# ----------------------------------------------------------------------

def primary_toolbutton_style(object_name: str) -> str:
    """
    Return a stylesheet for a primary QToolButton inside a toolbar.

    This is intended for key operational actions such as Send/Receive.

    Parameters
    ----------
    object_name : str
        The object name assigned to the QToolButton.

    Returns
    -------
    str
        A Qt stylesheet string scoped to the specific toolbutton.
    """
    return f"""
    
QToolButton#{object_name} {{
    background-color: {SELECT_BG};
    color: {TEXT};
    border: 1px solid {BUTTON_BORDER_HOVER};
    border-radius: 4px;
    padding: 4px 10px;
    font-weight: 600;
}}

QToolButton#{object_name}:hover {{
    background-color: {HOVER_BG};
    border: 1px solid {BUTTON_BORDER_HOVER};
}}

QToolButton#{object_name}:pressed {{
    background-color: {PRESSED_BG};
}}

QToolButton#{object_name}:disabled {{
    background-color: {PANEL_BG};
    color: {DISABLED_TEXT};
    border: 1px solid {LIGHT_BORDER};
}}
"""


# ----------------------------------------------------------------------
# Convenience helpers
# ----------------------------------------------------------------------

def apply_base_dialog_style(widget) -> None:
    """
    Apply the shared dialog/form stylesheet to a dialog or form widget.

    Parameters
    ----------
    widget : QWidget
        The target widget, typically a QDialog or configuration form.
    """
    widget.setStyleSheet(DIALOG_STYLE)


def apply_base_main_window_style(widget) -> None:
    """
    Apply the shared main window stylesheet to a main window.

    Parameters
    ----------
    widget : QWidget
        The target widget, typically a QMainWindow.
    """
    widget.setStyleSheet(MAIN_WINDOW_STYLE)


def apply_tree_style(widget, *, alternating_rows: bool = True) -> None:
    """
    Apply the shared tree style to a QTreeWidget or QTreeView-like widget.

    Parameters
    ----------
    widget : QWidget
        The tree widget/view to style.
    alternating_rows : bool, optional
        Whether to enable alternating row colors, by default True.
    """
    if hasattr(widget, "setAlternatingRowColors"):
        widget.setAlternatingRowColors(alternating_rows)
    widget.setStyleSheet(TREE_STYLE)


def apply_table_style(widget, *, alternating_rows: bool = True) -> None:
    """
    Apply the shared table style to a QTableWidget or QTableView-like widget.

    Parameters
    ----------
    widget : QWidget
        The table widget/view to style.
    alternating_rows : bool, optional
        Whether to enable alternating row colors, by default True.
    """
    if hasattr(widget, "setAlternatingRowColors"):
        widget.setAlternatingRowColors(alternating_rows)
    widget.setStyleSheet(TABLE_STYLE)


def apply_splitter_style(widget) -> None:
    """
    Apply the shared splitter style to a QSplitter.

    Parameters
    ----------
    widget : QSplitter
        The splitter to style.
    """
    widget.setStyleSheet(SPLITTER_STYLE)