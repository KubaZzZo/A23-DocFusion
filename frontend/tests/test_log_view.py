import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from docfusion_page import DocFusionWindow


def test_log_view_appends_incrementally_and_limits_blocks():
    app = QApplication.instance() or QApplication([])
    window = DocFusionWindow()

    assert window.log_view.maximumBlockCount() == 500

    for index in range(510):
        window.log(f"event-{index}")

    text = window.log_view.toPlainText()
    assert "等待操作" not in text
    assert "event-509" in text
    assert window.log_view.document().blockCount() <= 500
    window.close()
