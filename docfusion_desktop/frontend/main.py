"""Run the standalone DocFusion Qt redesign."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from docfusion_page import DocFusionWindow
from theme import qss


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyleSheet(qss())

    window = DocFusionWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
