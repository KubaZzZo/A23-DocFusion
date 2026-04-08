"""主窗口"""
import sys
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QStatusBar,
    QMenuBar, QMenu, QMessageBox, QVBoxLayout, QWidget, QComboBox,
    QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtGui import QPalette, QColor, QIcon, QPixmap, QPainter
try:
    from PyQt6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False
from ui.doc_panel import DocPanel
from ui.extract_panel import ExtractPanel
from ui.fill_panel import FillPanel
from ui.crawler_panel import CrawlerPanel
from ui.dashboard_panel import DashboardPanel
from ui.settings_dialog import SettingsDialog, apply_saved_settings
from ui.styles import GLOBAL_QSS, BG_MAIN, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY, PRIMARY, BORDER
from config import LLM_CONFIG


def _svg_icon(svg_str: str, size: int = 20) -> QIcon:
    """将 SVG 字符串转为 QIcon，QtSvg 不可用时返回空图标"""
    if not _HAS_SVG:
        return QIcon()
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


# 线条风格 SVG 图标（stroke-based, 24x24 viewBox）
_COLOR = "#5B8DEF"

ICON_DASHBOARD = f'''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
  fill="none" stroke="{_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="3" y="13" width="4" height="8" rx="1"/>
  <rect x="10" y="8" width="4" height="13" rx="1"/>
  <rect x="17" y="3" width="4" height="18" rx="1"/>
</svg>'''

ICON_DOC = f'''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
  fill="none" stroke="{_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/>
  <polyline points="14 2 14 8 20 8"/>
  <line x1="8" y1="13" x2="16" y2="13"/>
  <line x1="8" y1="17" x2="13" y2="17"/>
</svg>'''

ICON_SEARCH = f'''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
  fill="none" stroke="{_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="11" cy="11" r="8"/>
  <line x1="21" y1="21" x2="16.65" y2="16.65"/>
  <line x1="8" y1="11" x2="14" y2="11"/>
  <line x1="11" y1="8" x2="11" y2="14"/>
</svg>'''

ICON_TABLE = f'''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
  fill="none" stroke="{_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="3" y="3" width="18" height="18" rx="2"/>
  <line x1="3" y1="9" x2="21" y2="9"/>
  <line x1="3" y1="15" x2="21" y2="15"/>
  <line x1="9" y1="3" x2="9" y2="21"/>
  <line x1="15" y1="3" x2="15" y2="21"/>
</svg>'''

ICON_GLOBE = f'''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
  fill="none" stroke="{_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/>
  <line x1="2" y1="12" x2="22" y2="12"/>
  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
</svg>'''

ICON_SETTINGS = f'''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
  fill="none" stroke="{_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="3"/>
  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33
    1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06
    a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15 1.65 1.65 0 0 0 3.17 14H3a2 2 0 0 1 0-4h.09
    A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0
    9 4.68 1.65 1.65 0 0 0 10 3.17V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33
    l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4
    h-.09a1.65 1.65 0 0 0-1.51 1z"/>
</svg>'''


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DocFusion - 文档理解与多源数据融合系统")
        self.setMinimumSize(1100, 750)

        # 菜单栏
        self._init_menu()

        # 中心区域
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 顶部工具栏
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
            }
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 8, 16, 8)

        # 品牌标识
        brand = QLabel("DocFusion")
        brand.setStyleSheet("font-size: 16px; font-weight: bold; color: #5B8DEF; background: transparent;")
        top_layout.addWidget(brand)
        ver = QLabel("v1.0")
        ver.setStyleSheet("font-size: 10px; color: #CCC; background: transparent; margin-top: 4px;")
        top_layout.addWidget(ver)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #E0E0E0; background: transparent;")
        sep.setFixedHeight(24)
        top_layout.addWidget(sep)

        # LLM 引擎选择
        llm_label = QLabel("LLM引擎")
        llm_label.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
        top_layout.addWidget(llm_label)
        self.llm_combo = QComboBox()
        self.llm_combo.addItems(["ollama (本地)", "openai (云端)"])
        self.llm_combo.setCurrentIndex(0 if LLM_CONFIG["provider"] == "ollama" else 1)
        self.llm_combo.currentIndexChanged.connect(self._on_llm_changed)
        self.llm_combo.setFixedWidth(160)
        top_layout.addWidget(self.llm_combo)

        # LLM 状态指示灯
        self.lbl_llm_status = QLabel("● 就绪")
        self.lbl_llm_status.setStyleSheet("font-size: 11px; color: #52C41A; background: transparent;")
        top_layout.addWidget(self.lbl_llm_status)

        top_layout.addStretch()

        # 设置按钮
        self.btn_settings = QPushButton(_svg_icon(ICON_SETTINGS), " 设置")
        self.btn_settings.setFixedWidth(90)
        self.btn_settings.clicked.connect(self._open_settings)
        top_layout.addWidget(self.btn_settings)

        layout.addWidget(top_bar)

        # Tab页
        self.tabs = QTabWidget()
        self.dashboard_panel = DashboardPanel()
        self.doc_panel = DocPanel()
        self.extract_panel = ExtractPanel()
        self.fill_panel = FillPanel()
        self.crawler_panel = CrawlerPanel()

        self.tabs.addTab(self.dashboard_panel, _svg_icon(ICON_DASHBOARD), "数据概览")
        self.tabs.addTab(self.doc_panel, _svg_icon(ICON_DOC), "文档智能操作")
        self.tabs.addTab(self.extract_panel, _svg_icon(ICON_SEARCH), "信息提取")
        self.tabs.addTab(self.fill_panel, _svg_icon(ICON_TABLE), "表格填写")
        self.tabs.addTab(self.crawler_panel, _svg_icon(ICON_GLOBE), "新闻爬虫")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

        self.setCentralWidget(central)

        # 状态栏
        self.statusBar().showMessage("就绪")

        # 启动API服务
        self._start_api()

    def _init_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("文件")
        file_menu.addAction("设置", self._open_settings)
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close)

        help_menu = menu_bar.addMenu("帮助")
        help_menu.addAction("关于", self._show_about)

    def _on_llm_changed(self, index):
        LLM_CONFIG["provider"] = "ollama" if index == 0 else "openai"
        provider = LLM_CONFIG["provider"]
        self.lbl_llm_status.setText(f"● 已切换")
        self.lbl_llm_status.setStyleSheet("font-size: 11px; color: #FAAD14; background: transparent;")
        self.statusBar().showMessage(f"已切换LLM引擎: {provider}")

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def _on_tab_changed(self, index):
        if index == 0:
            self.dashboard_panel.refresh()

    def _start_api(self):
        from api.server import start_api_server
        t = threading.Thread(target=start_api_server, daemon=True)
        t.start()
        self.statusBar().showMessage("API服务已启动 (http://127.0.0.1:8000)")

    def _show_about(self):
        QMessageBox.about(self, "关于",
                          "DocFusion v1.0\n文档理解与多源数据融合系统\nA23赛题参赛作品")


def _apply_light_palette(app: QApplication):
    """设置浅色调色板"""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG_MAIN))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F5F7FA"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Link, QColor(PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(PRIMARY))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_SECONDARY))
    palette.setColor(QPalette.ColorRole.Mid, QColor(BORDER))
    palette.setColor(QPalette.ColorRole.Light, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#C0C0C0"))
    app.setPalette(palette)


def run_app():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _apply_light_palette(app)
    app.setStyleSheet(GLOBAL_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
