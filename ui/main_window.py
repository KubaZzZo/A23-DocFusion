"""主窗口"""
import sys
import threading

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget

try:
    from PyQt6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False

from config import LLM_CONFIG
from ui.crawler_panel import CrawlerPanel
from ui.dashboard_panel import DashboardPanel
from ui.doc_panel import DocPanel
from ui.extract_panel import ExtractPanel
from ui.fill_panel import FillPanel
from ui.main_status_bar import MainStatusBar, llm_status_snapshot
from ui.settings_dialog import SettingsDialog
from ui.styles import BG_CARD, BG_MAIN, BORDER, GLOBAL_QSS, PRIMARY, TEXT_PRIMARY, TEXT_SECONDARY


def _svg_icon(svg_str: str, size: int = 20) -> QIcon:
    if not _HAS_SVG:
        return QIcon()
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


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


def _llm_status_snapshot(config: dict | None = None) -> dict:
    return llm_status_snapshot(config)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DocFusion - 文档理解与多源数据融合系统")
        self.setMinimumSize(1100, 750)
        self._init_menu()

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.status_bar_widget = MainStatusBar(self._open_settings, self._on_provider_changed)
        layout.addWidget(self.status_bar_widget)

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
        self.statusBar().showMessage("就绪")
        self._start_api()

    def _init_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("文件")
        file_menu.addAction("设置", self._open_settings)
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close)

        help_menu = menu_bar.addMenu("帮助")
        help_menu.addAction("关于", self._show_about)

    def _on_provider_changed(self, provider):
        self.statusBar().showMessage(f"当前 LLM 提供方: {provider}")

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()
        self._sync_status_bar_to_config()

    def _refresh_llm_status(self):
        self.status_bar_widget.refresh_llm_status()

    def _sync_status_bar_to_config(self):
        self.status_bar_widget.llm_combo.setCurrentIndex(0 if LLM_CONFIG["provider"] == "ollama" else 1)
        self.status_bar_widget.refresh_llm_status()

    def _on_tab_changed(self, index):
        if index == 0:
            self.dashboard_panel.refresh()

    def _start_api(self):
        from api.server import start_api_server

        t = threading.Thread(target=start_api_server, daemon=True)
        t.start()
        self.statusBar().showMessage("API 服务已启动 (http://127.0.0.1:8000)")

    def _show_about(self):
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.about(
            self,
            "关于",
            "DocFusion v1.0\n文档理解与多源数据融合系统\nA23 赛题参赛作品",
        )


def _apply_light_palette(app: QApplication):
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
