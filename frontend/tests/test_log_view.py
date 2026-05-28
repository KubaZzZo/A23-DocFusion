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


def test_log_view_does_not_read_full_log_for_each_append(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = DocFusionWindow()
    calls = []

    def fail_to_plain_text():
        calls.append(True)
        raise AssertionError("log() should not rebuild or scan the full log text")

    monkeypatch.setattr(window.log_view, "toPlainText", fail_to_plain_text)

    window.log("one event")

    assert calls == []
    assert "one event" in window.log_view.document().toPlainText()
    window.close()
