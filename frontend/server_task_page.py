"""Server task page builder for the DocFusion desktop window."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from theme import INVERSE_ELEVATED, INVERSE_TEXT


@dataclass(frozen=True)
class ServerTaskWidgets:
    url_input: QLineEdit
    token_input: QLineEdit
    connection_label: QLabel
    instruction: QPlainTextEdit
    files_label: QLabel
    status_view: QPlainTextEdit

    @classmethod
    def from_window(cls, window) -> "ServerTaskWidgets":
        return cls(
            url_input=window.server_task_url_input,
            token_input=window.server_task_token_input,
            connection_label=window.server_task_connection_label,
            instruction=window.server_task_instruction,
            files_label=window.server_task_files_label,
            status_view=window.server_task_status_view,
        )


def build_server_task_panel(window) -> QFrame:
    """Build and attach the server task widgets used by DocFusionWindow."""
    task_panel = QFrame()
    task_panel.setObjectName("softPanel")
    task_layout = QVBoxLayout(task_panel)
    task_layout.setContentsMargins(16, 14, 16, 14)
    task_layout.setSpacing(12)
    task_layout.addWidget(window._panel_heading("自然语言任务", ""))

    task_config = QGridLayout()
    task_config.setHorizontalSpacing(10)
    task_config.setVerticalSpacing(8)
    window.server_task_url_input = QLineEdit(window.server_task_config.base_url)
    window.server_task_token_input = QLineEdit()
    window.server_task_token_input.setText(window.server_task_config.token)
    window.server_task_token_input.setEchoMode(QLineEdit.Password)
    window.server_task_token_input.setPlaceholderText("Bearer token")
    task_config.addWidget(QLabel("服务器地址"), 0, 0)
    task_config.addWidget(window.server_task_url_input, 0, 1)
    task_config.addWidget(QLabel("Token"), 1, 0)
    task_config.addWidget(window.server_task_token_input, 1, 1)
    task_layout.addLayout(task_config)

    task_config_actions = QHBoxLayout()
    check = QPushButton("检测连接")
    check.setObjectName("secondary")
    check.clicked.connect(window.check_server_task_health)
    task_config_actions.addWidget(check)
    save_config = QPushButton("保存配置")
    save_config.setObjectName("secondary")
    save_config.clicked.connect(window.save_server_task_settings)
    task_config_actions.addWidget(save_config)
    task_config_actions.addStretch()
    task_layout.addLayout(task_config_actions)

    window.server_task_connection_label = QLabel("服务器任务会优先使用当前选中文档；未选中文档时可选择临时文件。")
    window.server_task_connection_label.setObjectName("muted")
    window.server_task_connection_label.setWordWrap(True)
    task_layout.addWidget(window.server_task_connection_label)

    window.server_task_instruction = QPlainTextEdit()
    window.server_task_instruction.setMinimumHeight(82)
    window.server_task_instruction.setPlaceholderText("例如：OCR 后提取金额、日期和供应商，或 convert this file to PDF")
    task_layout.addWidget(window.server_task_instruction)

    file_actions = QHBoxLayout()
    add_files = QPushButton("选择临时文件")
    add_files.setObjectName("secondary")
    add_files.clicked.connect(window.add_server_task_files)
    file_actions.addWidget(add_files)
    clear_files = QPushButton("清空临时文件")
    clear_files.setObjectName("secondary")
    clear_files.clicked.connect(window.clear_server_task_files)
    file_actions.addWidget(clear_files)
    file_actions.addStretch()
    task_layout.addLayout(file_actions)

    window.server_task_files_label = QLabel("输入文件：当前未选择文档，也未选择临时文件")
    window.server_task_files_label.setObjectName("muted")
    window.server_task_files_label.setWordWrap(True)
    task_layout.addWidget(window.server_task_files_label)

    run_actions = QHBoxLayout()
    submit = QPushButton("提交任务")
    submit.clicked.connect(window.submit_server_task)
    run_actions.addWidget(submit)
    refresh = QPushButton("刷新状态")
    refresh.setObjectName("secondary")
    refresh.clicked.connect(window.refresh_server_task_status)
    run_actions.addWidget(refresh)
    download = QPushButton("下载结果")
    download.setObjectName("secondary")
    download.clicked.connect(window.download_server_task_result)
    run_actions.addWidget(download)
    run_actions.addStretch()
    task_layout.addLayout(run_actions)

    window.server_task_status_view = QPlainTextEdit()
    window.server_task_status_view.setReadOnly(True)
    window.server_task_status_view.setMinimumHeight(150)
    window.server_task_status_view.setPlainText("等待提交服务器任务...")
    window.server_task_status_view.setStyleSheet(
        f"background: {INVERSE_ELEVATED}; color: {INVERSE_TEXT}; "
        "border: 1px solid rgba(250,249,245,0.14); border-radius: 8px; "
        "font-family: Consolas; font-size: 13px; padding: 12px;"
    )
    task_layout.addWidget(window.server_task_status_view)
    return task_panel
