import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QPlainTextEdit

from docfusion_page import DocFusionWindow
from server_task_page import ServerTaskWidgets


def test_server_task_widgets_are_built_by_dedicated_page_module():
    app = QApplication.instance() or QApplication([])
    window = DocFusionWindow()
    try:
        widgets = ServerTaskWidgets.from_window(window)

        assert widgets.url_input is window.server_task_url_input
        assert widgets.token_input is window.server_task_token_input
        assert widgets.status_view is window.server_task_status_view
        assert isinstance(widgets.status_view, QPlainTextEdit)
    finally:
        window.close()
