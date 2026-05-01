"""Small shared UI presentation helpers."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QProgressBar, QTextEdit, QVBoxLayout, QWidget


PANEL_MARGINS = (10, 10, 10, 10)
PANEL_SPACING = 8
LOG_HEIGHT = 132


def apply_panel_density(layout: QVBoxLayout, *, margins: tuple[int, int, int, int] = PANEL_MARGINS, spacing: int = PANEL_SPACING):
    """Apply consistent margins and spacing to a top-level panel layout."""

    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


def set_log_height(widget: QTextEdit, height: int = LOG_HEIGHT):
    """Keep log panes compact and predictable across panels."""

    widget.setMinimumHeight(height)
    widget.setMaximumHeight(height)
    return widget


def mark_primary(button: QPushButton) -> QPushButton:
    """Mark a button as the main action in its local workflow."""

    button.setObjectName("")
    return button


def mark_secondary(button: QPushButton) -> QPushButton:
    """Mark a button as a supporting action."""

    button.setObjectName("secondary")
    return button


def mark_danger(button: QPushButton) -> QPushButton:
    """Mark a button as destructive or reset-oriented."""

    button.setObjectName("danger")
    return button


class EmptyState(QWidget):
    """Consistent empty-state block for panels and dashboards."""

    def __init__(self, title: str, detail: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setStyleSheet("""
            QWidget#emptyState {
                background-color: #FAFBFC;
                border: 1px dashed #DADFE8;
                border-radius: 8px;
            }
            QLabel#emptyStateTitle {
                color: #888888;
                font-size: 13px;
                font-weight: 600;
                background-color: transparent;
            }
            QLabel#emptyStateDetail {
                color: #A8ADB7;
                font-size: 12px;
                background-color: transparent;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(6)
        layout.addStretch()

        self.title = QLabel(title)
        self.title.setObjectName("emptyStateTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        self.detail = QLabel(detail)
        self.detail.setObjectName("emptyStateDetail")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)

        layout.addStretch()

    def set_message(self, title: str, detail: str = ""):
        self.title.setText(title)
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))


def set_busy_state(
    button: QPushButton,
    progress: QProgressBar,
    busy: bool,
    *,
    busy_text: str | None = None,
    idle_text: str | None = None,
    label: QLabel | None = None,
    label_text: str | None = None,
):
    """Apply a consistent busy/idle state to a button and progress bar."""

    button.setEnabled(not busy)
    if busy:
        if busy_text is not None:
            button.setText(busy_text)
        progress.setVisible(True)
        progress.setRange(0, 0)
        if label is not None and label_text is not None:
            label.setText(label_text)
    else:
        if idle_text is not None:
            button.setText(idle_text)
        progress.setVisible(False)
