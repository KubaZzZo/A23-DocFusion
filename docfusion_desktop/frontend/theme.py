"""Warm, restrained Qt theme inspired by C:/Users/liukun/Desktop/design.md."""

CANVAS = "#faf9f5"
SECTION = "#f5f0e8"
CARD = "#efe9de"
ELEVATED = "#fffdf8"
INVERSE = "#181715"
INVERSE_ELEVATED = "#252320"

INK = "#141413"
BODY = "#3d3d3a"
MUTED = "#6c6a64"
SUBTLE = "#8c8982"
INVERSE_TEXT = "#faf9f5"
INVERSE_MUTED = "#a09d96"

PRIMARY = "#cc785c"
PRIMARY_HOVER = "#a9583e"
PRIMARY_SOFT = "#f6ded6"
TEAL = "#2f7f72"
TEAL_SOFT = "#d9eee8"
AMBER = "#9a651d"
AMBER_SOFT = "#f5e3c8"
BLUE = "#4f7db8"
GREEN = "#4f9f63"
RED = "#c64545"

BORDER = "#e6dfd8"
BORDER_STRONG = "#d7cbbd"

FONT_SANS = '"Microsoft YaHei UI", "Noto Sans SC", "Segoe UI", Arial, sans-serif'
FONT_SERIF = '"Noto Serif SC", "Source Han Serif SC", "SimSun", Georgia, serif'
FONT_MONO = '"JetBrains Mono", Consolas, monospace'


def qss() -> str:
    return f"""
    QWidget {{
        background: {CANVAS};
        color: {BODY};
        font-family: {FONT_SANS};
        font-size: 14px;
    }}

    QMainWindow {{
        background: {CANVAS};
    }}

    QLabel#appTitle {{
        color: {INK};
        background: transparent;
        font-family: {FONT_SERIF};
        font-size: 22px;
        font-weight: 500;
    }}

    QLabel {{
        background: transparent;
    }}

    QLabel#heroTitle {{
        color: {INK};
        background: transparent;
        font-family: {FONT_SERIF};
        font-size: 30px;
        font-weight: 500;
        line-height: 1.16;
    }}

    QLabel#sectionTitle {{
        color: {INK};
        background: transparent;
        font-size: 20px;
        font-weight: 650;
    }}

    QLabel#panelTitle {{
        color: {INK};
        background: transparent;
        font-size: 15px;
        font-weight: 650;
    }}

    QLabel#muted {{
        color: {MUTED};
        background: transparent;
        font-size: 13px;
        line-height: 1.45;
    }}

    QLabel#caption {{
        color: {SUBTLE};
        background: transparent;
        font-size: 12px;
    }}

    QLabel#fieldLabel {{
        color: {BODY};
        background: transparent;
        font-size: 13px;
        font-weight: 600;
    }}

    QPushButton {{
        background: {PRIMARY};
        color: white;
        border: 0;
        border-radius: 8px;
        padding: 9px 16px;
        font-size: 14px;
        font-weight: 600;
    }}

    QPushButton:hover {{
        background: {PRIMARY_HOVER};
    }}

    QPushButton#secondary {{
        background: {ELEVATED};
        color: {INK};
        border: 1px solid {BORDER};
    }}

    QPushButton#secondary:hover {{
        background: {SECTION};
        border-color: {BORDER_STRONG};
    }}

    QPushButton#navButton {{
        background: transparent;
        color: {MUTED};
        border: 0;
        border-radius: 8px;
        padding: 10px 12px;
        text-align: left;
        font-weight: 550;
    }}

    QPushButton#navButton:hover {{
        background: {SECTION};
        color: {INK};
    }}

    QPushButton#navButton:checked {{
        background: {CARD};
        color: {INK};
    }}

    QFrame#sidebar {{
        background: {CANVAS};
        border-right: 1px solid {BORDER};
    }}

    QFrame#paperPanel {{
        background: {ELEVATED};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}

    QFrame#softPanel {{
        background: {SECTION};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}

    QFrame#darkPanel {{
        background: {INVERSE};
        border: 1px solid {INVERSE_ELEVATED};
        border-radius: 8px;
    }}

    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
        background: {ELEVATED};
        color: {INK};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 9px 11px;
        selection-background-color: {PRIMARY_SOFT};
        selection-color: {INK};
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
        border: 1px solid {PRIMARY};
    }}

    QComboBox {{
        padding-right: 28px;
    }}

    QComboBox::drop-down {{
        width: 26px;
        border: 0;
        background: transparent;
    }}

    QComboBox::down-arrow {{
        width: 0;
        height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {SUBTLE};
        margin-right: 8px;
    }}

    QComboBox QAbstractItemView {{
        background: {ELEVATED};
        color: {INK};
        border: 1px solid {BORDER};
        selection-background-color: {PRIMARY_SOFT};
        selection-color: {INK};
        padding: 4px;
    }}

    QTableWidget {{
        background: {ELEVATED};
        alternate-background-color: {CANVAS};
        color: {BODY};
        border: 1px solid {BORDER};
        border-radius: 8px;
        gridline-color: {BORDER};
        selection-background-color: {PRIMARY_SOFT};
        selection-color: {INK};
    }}

    QHeaderView::section {{
        background: {SECTION};
        color: {MUTED};
        border: 0;
        border-bottom: 1px solid {BORDER};
        padding: 9px 10px;
        font-size: 12px;
        font-weight: 650;
    }}

    QProgressBar {{
        background: {SECTION};
        border: 1px solid {BORDER};
        border-radius: 6px;
        height: 8px;
        text-align: center;
        color: transparent;
    }}

    QProgressBar::chunk {{
        background: {PRIMARY};
        border-radius: 5px;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 4px 0;
    }}

    QScrollBar::handle:vertical {{
        background: {BORDER_STRONG};
        border-radius: 4px;
        min-height: 36px;
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    """
