"""Run the standalone DocFusion Qt redesign."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from docfusion_page import DocFusionWindow
from theme import qss


APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
APP_ICON = APP_ROOT / "assets" / "docfusion_icon.ico"


def main() -> int:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DocFusion.Desktop")
        except Exception:
            pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    if APP_ICON.exists():
        app.setWindowIcon(QIcon(str(APP_ICON)))
    app.setStyleSheet(qss())

    window = DocFusionWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
