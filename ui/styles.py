"""全局QSS样式表 - 浅色柔和风格"""

# 颜色常量
PRIMARY = "#5B8DEF"
PRIMARY_HOVER = "#4A7DE0"
PRIMARY_PRESSED = "#3A6DD0"
SUCCESS = "#52C41A"
WARNING = "#FAAD14"
DANGER = "#FF4D4F"

BG_MAIN = "#F7F8FA"
BG_CARD = "#FFFFFF"
BG_INPUT = "#FFFFFF"

TEXT_PRIMARY = "#333333"
TEXT_SECONDARY = "#888888"
BORDER = "#E0E0E0"
BORDER_FOCUS = "#5B8DEF"

TABLE_ROW_ALT = "#F5F7FA"
TABLE_HEADER_BG = "#EEF2F9"

GLOBAL_QSS = f"""
/* ===== 全局 ===== */
QMainWindow, QWidget {{
    background-color: {BG_MAIN};
    color: {TEXT_PRIMARY};
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}}

/* ===== 菜单栏 ===== */
QMenuBar {{
    background-color: {BG_CARD};
    border-bottom: 1px solid {BORDER};
    padding: 2px 0;
}}
QMenuBar::item {{
    padding: 6px 14px;
    border-radius: 4px;
    margin: 2px 2px;
}}
QMenuBar::item:selected {{
    background-color: {TABLE_ROW_ALT};
}}
QMenu {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 28px;
}}
QMenu::item:selected {{
    background-color: {TABLE_ROW_ALT};
    color: {PRIMARY};
}}

/* ===== 按钮 ===== */
QPushButton {{
    background-color: {PRIMARY};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    font-weight: 500;
    min-height: 18px;
}}
QPushButton:hover {{
    background-color: {PRIMARY_HOVER};
}}
QPushButton:pressed {{
    background-color: {PRIMARY_PRESSED};
}}
QPushButton:disabled {{
    background-color: #C0C4CC;
    color: #FFFFFF;
}}

/* ===== 输入框 ===== */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    selection-background-color: {PRIMARY};
    selection-color: white;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {BORDER_FOCUS};
}}

/* ===== 下拉框 ===== */
QComboBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 20px;
}}
QComboBox:hover {{
    border: 1px solid {BORDER_FOCUS};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    selection-background-color: {TABLE_ROW_ALT};
    selection-color: {PRIMARY};
}}

/* ===== Tab栏 ===== */
QTabWidget::pane {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: -1px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    padding: 10px 22px;
    margin-right: 2px;
    border-bottom: 2px solid transparent;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {PRIMARY};
    border-bottom: 2px solid {PRIMARY};
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT_PRIMARY};
    border-bottom: 2px solid #D0D0D0;
}}

/* ===== 表格 ===== */
QTableWidget {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: #EBEEF5;
    alternate-background-color: {TABLE_ROW_ALT};
}}
QTableWidget::item {{
    padding: 6px 8px;
}}
QTableWidget::item:selected {{
    background-color: #E8F0FE;
    color: {TEXT_PRIMARY};
}}
QHeaderView::section {{
    background-color: {TABLE_HEADER_BG};
    color: {TEXT_PRIMARY};
    font-weight: bold;
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid #E8E8E8;
}}

/* ===== 列表 ===== */
QListWidget {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 4px;
}}
QListWidget::item:selected {{
    background-color: #E8F0FE;
    color: {PRIMARY};
}}
QListWidget::item:hover:!selected {{
    background-color: {TABLE_ROW_ALT};
}}

/* ===== 进度条 ===== */
QProgressBar {{
    background-color: #E8E8E8;
    border: none;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    font-size: 11px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {PRIMARY}, stop:1 #7EB8FF);
    border-radius: 6px;
}}

/* ===== 分组框 ===== */
QGroupBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 20px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    color: {PRIMARY};
}}

/* ===== 分割器 ===== */
QSplitter::handle {{
    background-color: {BORDER};
    width: 1px;
    margin: 4px 2px;
}}

/* ===== 滚动条 ===== */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: #C8C8C8;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: #A8A8A8;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background-color: #C8C8C8;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: #A8A8A8;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ===== 状态栏 ===== */
QStatusBar {{
    background-color: {BG_CARD};
    border-top: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}

/* ===== 工具提示 ===== */
QToolTip {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ===== 对话框 ===== */
QDialog {{
    background-color: {BG_MAIN};
}}

/* ===== 次要按钮 ===== */
QPushButton[objectName="secondary"] {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
}}
QPushButton[objectName="secondary"]:hover {{
    border-color: {PRIMARY};
    color: {PRIMARY};
}}
QPushButton[objectName="secondary"]:pressed {{
    background-color: {TABLE_ROW_ALT};
}}

/* ===== 标签 ===== */
QLabel {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
}}

/* ===== 复选框 ===== */
QCheckBox {{
    spacing: 6px;
    color: {TEXT_PRIMARY};
    background-color: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background-color: {PRIMARY};
    border-color: {PRIMARY};
}}

/* ===== SpinBox ===== */
QSpinBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 8px;
}}
QSpinBox:focus {{
    border: 1px solid {BORDER_FOCUS};
}}

/* ===== 消息框 ===== */
QMessageBox {{
    background-color: {BG_CARD};
}}
"""
