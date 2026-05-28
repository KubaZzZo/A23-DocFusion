"""A standalone redesigned Qt page backed by the DocFusion FastAPI service."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QThreadPool, QTimer, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from api_client import ApiError, DocFusionApiClient
from crawler_service import crawl_articles, news_sources
from server_task_client import ServerTaskClient, ServerTaskConfig, load_server_task_config, save_server_task_config
from local_services import (
    batch_extract_documents,
    clear_and_reextract_document,
    cross_document_entities,
    export_fusion_report,
    generate_crawled_documents,
    cloud_vendor_options,
    load_llm_provider_settings,
    save_llm_provider_settings,
    store_crawled_articles,
    test_llm_provider_settings,
)
from theme import (
    AMBER,
    AMBER_SOFT,
    BLUE,
    BODY,
    CARD,
    ELEVATED,
    GREEN,
    INK,
    INVERSE_ELEVATED,
    INVERSE_MUTED,
    INVERSE_TEXT,
    MUTED,
    PRIMARY,
    PRIMARY_SOFT,
    RED,
    TEAL,
    TEAL_SOFT,
)
from workers import ApiRunnable, ProgressApiRunnable


class MetricCard(QFrame):
    def __init__(self, title: str, tone: str = "primary"):
        super().__init__()
        self.setObjectName("paperPanel")
        marker_color = {"primary": PRIMARY, "teal": TEAL, "amber": AMBER, "blue": BLUE}.get(tone, PRIMARY)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        top = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("caption")
        top.addWidget(label)
        top.addStretch()
        dot = QLabel()
        dot.setFixedSize(9, 9)
        dot.setStyleSheet(f"background: {marker_color}; border-radius: 4px;")
        top.addWidget(dot)
        layout.addLayout(top)

        self.value_label = QLabel("...")
        self.value_label.setStyleSheet(f"color: {INK}; font-size: 28px; font-weight: 700;")
        layout.addWidget(self.value_label)

        self.helper_label = QLabel("等待后端数据")
        self.helper_label.setObjectName("muted")
        layout.addWidget(self.helper_label)

    def set_data(self, value: Any, helper: str) -> None:
        self.value_label.setText(str(value))
        self.helper_label.setText(helper)


class Tag(QLabel):
    def __init__(self, text: str, bg: str = PRIMARY_SOFT, fg: str = PRIMARY):
        super().__init__(text)
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 6px; "
            "padding: 4px 8px; font-size: 12px; font-weight: 650;"
        )


class FieldBlock(QFrame):
    def __init__(self, title: str, hint: str = ""):
        super().__init__()
        self.setObjectName("softPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        label = QLabel(title)
        label.setObjectName("caption")
        layout.addWidget(label)

        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        layout.addLayout(self.body)

        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("muted")
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)


class NavButton(QPushButton):
    def __init__(self, text: str):
        super().__init__(text)
        self.setObjectName("navButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)


class DocFusionWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DocFusion - 文档理解与数据融合系统")
        self.resize(1440, 920)
        self.setMinimumSize(1180, 760)

        self.client = DocFusionApiClient()
        self.pool = QThreadPool.globalInstance()
        self.nav_buttons: list[NavButton] = []
        self.documents: list[dict[str, Any]] = []
        self.entities: list[dict[str, Any]] = []
        self.articles: list[dict[str, Any]] = []
        self.crawled_preview: list[dict[str, Any]] = []
        self.fusion_rows: list[dict[str, Any]] = []
        self.selected_doc_id: int | None = None
        self.selected_article_id: int | None = None
        self.latest_template_id: int | None = None
        self.latest_task_id: int | None = None
        self.latest_server_task_id: str | None = None
        self.server_task_poll_count = 0
        self.server_task_max_polls = 120
        self.server_task_files: list[Path] = []
        self.server_task_defaults_path = Path(__file__).resolve().parent / "server_task.defaults.json"
        self.server_task_config_path = Path.home() / ".docfusion" / "server-task.json"
        self.server_task_config = load_server_task_config(self.server_task_config_path, self.server_task_defaults_path)
        self.api_process: subprocess.Popen | None = None
        self.source_checks: dict[str, QCheckBox] = {}

        self._build()
        QTimer.singleShot(200, self.check_health)

    def _build(self) -> None:
        shell = QWidget()
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(shell)

        root.addWidget(self._sidebar())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._workspace_page())
        self.stack.addWidget(self._document_page())
        self.stack.addWidget(self._fusion_page())
        self.stack.addWidget(self._articles_page())
        self.stack.addWidget(self._settings_page())
        root.addWidget(self.stack, 1)
        self._activate_nav(0)

    def _sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(22, 26, 22, 22)
        layout.setSpacing(14)

        brand_row = QHBoxLayout()
        logo = QLabel("D")
        logo.setFixedSize(42, 42)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            f"background: {PRIMARY}; color: white; border-radius: 8px; "
            "font-family: Georgia; font-size: 23px; font-weight: 500;"
        )
        brand_row.addWidget(logo)
        brand_text = QVBoxLayout()
        title = QLabel("DocFusion")
        title.setObjectName("appTitle")
        subtitle = QLabel("文档理解与数据融合")
        subtitle.setObjectName("caption")
        brand_text.addWidget(title)
        brand_text.addWidget(subtitle)
        brand_row.addLayout(brand_text)
        layout.addLayout(brand_row)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {CARD};")
        layout.addWidget(divider)

        for index, label in enumerate(["工作台", "文档库", "融合流程", "文章库", "系统设置"]):
            btn = NavButton(label)
            btn.clicked.connect(lambda checked=False, i=index: self._activate_nav(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()
        status = QFrame()
        status.setObjectName("softPanel")
        status_layout = QVBoxLayout(status)
        status_layout.setContentsMargins(14, 14, 14, 14)
        status_layout.setSpacing(8)
        self.api_status_tag = Tag("正在检测后端", AMBER_SOFT, AMBER)
        status_layout.addWidget(self.api_status_tag)
        self.api_status_text = QLabel("连接 https://docx.zhuoruan.xyz/api")
        self.api_status_text.setObjectName("muted")
        self.api_status_text.setWordWrap(True)
        status_layout.addWidget(self.api_status_text)
        layout.addWidget(status)
        return sidebar

    def _activate_nav(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

    def _page_shell(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        canvas = QWidget()
        layout = QVBoxLayout(canvas)
        layout.setContentsMargins(42, 34, 42, 42)
        layout.setSpacing(24)
        scroll.setWidget(canvas)
        outer.addWidget(scroll)
        return page, layout

    def _header(self, title: str, subtitle: str, action: str | None = None, callback: Callable[[], None] | None = None) -> QFrame:
        header = QFrame()
        header.setObjectName("softPanel")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(22, 10, 22, 10)
        layout.setSpacing(18)

        text_col = QVBoxLayout()
        h1 = QLabel(title)
        h1.setObjectName("heroTitle")
        text_col.addWidget(h1)
        if subtitle:
            body = QLabel(subtitle)
            body.setObjectName("muted")
            body.setWordWrap(True)
            body.setMaximumWidth(780)
            text_col.addWidget(body)
        layout.addLayout(text_col, 1)

        if action:
            btn = QPushButton(action)
            btn.setCursor(Qt.PointingHandCursor)
            if callback:
                btn.clicked.connect(callback)
            layout.addWidget(btn, 0, Qt.AlignTop)
        header.setMaximumHeight(66 if not subtitle and not action else 92 if not subtitle else 116)
        return header

    def _workspace_page(self) -> QWidget:
        page, layout = self._page_shell()
        layout.addWidget(
            self._header(
                "让文档、模板和数据在一个安静的工作台里对齐",
                "",
                "刷新数据",
                self.refresh_all,
            )
        )

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(14)
        self.metric_docs = MetricCard("文档总数", "primary")
        self.metric_entities = MetricCard("实体总数", "teal")
        self.metric_templates = MetricCard("模板总数", "amber")
        self.metric_articles = MetricCard("文章总数", "blue")
        for i, card in enumerate([self.metric_docs, self.metric_entities, self.metric_templates, self.metric_articles]):
            metrics.addWidget(card, 0, i)
        layout.addLayout(metrics)

        work = QGridLayout()
        work.setHorizontalSpacing(18)
        work.setVerticalSpacing(18)
        work.addWidget(self._pipeline_panel(), 0, 0, 2, 1)
        work.addWidget(self._model_panel(), 0, 1)
        work.addWidget(self._review_panel(), 1, 1)
        work.setColumnStretch(0, 3)
        work.setColumnStretch(1, 2)
        layout.addLayout(work)

        recent_grid = QGridLayout()
        recent_grid.setHorizontalSpacing(18)
        recent_grid.setVerticalSpacing(18)
        recent_grid.addWidget(self._recent_documents_panel(), 0, 0)
        recent_grid.addWidget(self._recent_articles_panel(), 0, 1)
        recent_grid.setColumnStretch(0, 1)
        recent_grid.setColumnStretch(1, 1)
        layout.addLayout(recent_grid)
        layout.addStretch()
        return page

    def _recent_documents_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("paperPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(self._panel_heading("最近文档", ""))
        self.recent_docs_list = QVBoxLayout()
        self.recent_docs_list.setSpacing(8)
        layout.addLayout(self.recent_docs_list)
        btn = QPushButton("打开文档库")
        btn.setObjectName("secondary")
        btn.clicked.connect(lambda: self._activate_nav(1))
        layout.addWidget(btn, 0, Qt.AlignLeft)
        return panel

    def _recent_articles_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("paperPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(self._panel_heading("最近文章", ""))
        self.recent_articles_list = QVBoxLayout()
        self.recent_articles_list.setSpacing(8)
        layout.addLayout(self.recent_articles_list)
        btn = QPushButton("打开文章库")
        btn.setObjectName("secondary")
        btn.clicked.connect(lambda: self._activate_nav(3))
        layout.addWidget(btn, 0, Qt.AlignLeft)
        return panel

    def _pipeline_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("paperPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(16)
        layout.addWidget(self._panel_heading("接口工作流", ""))
        steps = [
            ("01", "上传文档", "导入资料", 100, TEAL),
            ("02", "解析文档", "读取正文与结构", 75, PRIMARY),
            ("03", "抽取实体", "识别人名、机构和关键字段", 55, AMBER),
            ("04", "模板填充", "生成结构化结果", 35, BLUE),
        ]
        for code, name, desc, progress, color in steps:
            row = QFrame()
            row.setObjectName("softPanel")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)
            code_label = QLabel(code)
            code_label.setFixedWidth(38)
            code_label.setAlignment(Qt.AlignCenter)
            code_label.setStyleSheet(
                f"background: {color}; color: white; border-radius: 6px; "
                "font-size: 13px; font-weight: 700; padding: 7px 0;"
            )
            row_layout.addWidget(code_label)
            text = QVBoxLayout()
            title = QLabel(name)
            title.setObjectName("panelTitle")
            text.addWidget(title)
            sub = QLabel(desc)
            sub.setObjectName("muted")
            text.addWidget(sub)
            row_layout.addLayout(text, 1)
            bar = QProgressBar()
            bar.setFixedWidth(150)
            bar.setValue(progress)
            row_layout.addWidget(bar)
            layout.addWidget(row)
        return panel

    def _model_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("darkPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        title = QLabel("接口返回预览")
        title.setStyleSheet(f"color: {INVERSE_TEXT}; font-size: 16px; font-weight: 650;")
        layout.addWidget(title)
        self.api_preview = QPlainTextEdit()
        self.api_preview.setReadOnly(True)
        self.api_preview.setPlainText("等待刷新后端数据...")
        self.api_preview.setStyleSheet(
            f"background: {INVERSE_ELEVATED}; color: {INVERSE_TEXT}; "
            "border: 1px solid rgba(250,249,245,0.14); border-radius: 8px; "
            "font-family: Consolas; font-size: 13px; padding: 12px;"
        )
        layout.addWidget(self.api_preview)
        hint = QLabel("深色区只呈现调试和模型/接口输出，主流程保持安静。")
        hint.setStyleSheet(f"color: {INVERSE_MUTED}; font-size: 12px;")
        layout.addWidget(hint)
        return panel

    def _review_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("paperPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(self._panel_heading("当前选择", ""))
        self.selected_doc_label = QLabel("尚未选择文档")
        self.selected_doc_label.setObjectName("muted")
        self.selected_doc_label.setWordWrap(True)
        layout.addWidget(self.selected_doc_label)
        for label, callback in [
            ("解析选中文档", self.parse_selected_document),
            ("抽取实体", self.extract_selected_document),
            ("删除文档", self.delete_selected_document),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("secondary" if label != "删除文档" else "")
            btn.clicked.connect(callback)
            layout.addWidget(btn)
        return panel

    def _document_page(self) -> QWidget:
        page, layout = self._page_shell()
        layout.addWidget(self._header("文档库", ""))

        tools = QHBoxLayout()
        upload = QPushButton("上传文档")
        upload.clicked.connect(self.upload_document)
        tools.addWidget(upload)
        refresh = QPushButton("刷新")
        refresh.setObjectName("secondary")
        refresh.clicked.connect(self.load_documents)
        tools.addWidget(refresh)
        batch = QPushButton("批量提取")
        batch.setObjectName("secondary")
        batch.clicked.connect(self.batch_extract_documents)
        tools.addWidget(batch)
        parse = QPushButton("解析")
        parse.setObjectName("secondary")
        parse.clicked.connect(self.parse_selected_document)
        tools.addWidget(parse)
        extract = QPushButton("抽取")
        extract.setObjectName("secondary")
        extract.clicked.connect(self.extract_selected_document)
        tools.addWidget(extract)
        delete = QPushButton("删除")
        delete.clicked.connect(self.delete_selected_document)
        tools.addWidget(delete)
        tools.addStretch()
        layout.addLayout(tools)

        splitter = QSplitter(Qt.Horizontal)

        table_panel = QFrame()
        table_panel.setObjectName("paperPanel")
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(18, 16, 18, 18)
        table_layout.setSpacing(12)
        table_layout.addWidget(self._panel_heading("文档列表", ""))

        self.documents_empty = QLabel("暂无文档。点击“上传文档”添加第一份资料。")
        self.documents_empty.setObjectName("muted")
        self.documents_empty.setWordWrap(True)
        table_layout.addWidget(self.documents_empty)

        self.documents_table = QTableWidget(0, 5)
        self.documents_table.setHorizontalHeaderLabels(["ID", "文件名", "类型", "解析状态", "创建时间"])
        self.documents_table.verticalHeader().setVisible(False)
        self.documents_table.setAlternatingRowColors(True)
        self.documents_table.horizontalHeader().setStretchLastSection(True)
        self.documents_table.setMinimumHeight(360)
        self.documents_table.itemSelectionChanged.connect(self._on_document_selected)
        table_layout.addWidget(self.documents_table)

        detail_panel = QFrame()
        detail_panel.setObjectName("paperPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(20, 18, 20, 20)
        detail_layout.setSpacing(12)
        detail_layout.addWidget(self._panel_heading("文档详情", ""))

        self.doc_detail_title = QLabel("尚未选择文档")
        self.doc_detail_title.setObjectName("sectionTitle")
        self.doc_detail_title.setWordWrap(True)
        detail_layout.addWidget(self.doc_detail_title)
        self.doc_detail_meta = QLabel("从左侧表格选择文档。")
        self.doc_detail_meta.setObjectName("muted")
        self.doc_detail_meta.setWordWrap(True)
        detail_layout.addWidget(self.doc_detail_meta)

        detail_actions = QHBoxLayout()
        parse_detail = QPushButton("解析")
        parse_detail.setObjectName("secondary")
        parse_detail.clicked.connect(self.parse_selected_document)
        detail_actions.addWidget(parse_detail)
        extract_detail = QPushButton("抽取实体")
        extract_detail.setObjectName("secondary")
        extract_detail.clicked.connect(self.extract_selected_document)
        detail_actions.addWidget(extract_detail)
        reextract_detail = QPushButton("清除并重抽")
        reextract_detail.setObjectName("secondary")
        reextract_detail.clicked.connect(self.reextract_selected_document)
        detail_actions.addWidget(reextract_detail)
        download_detail = QPushButton("下载/打开")
        download_detail.setObjectName("secondary")
        download_detail.clicked.connect(self.download_selected_document)
        detail_actions.addWidget(download_detail)
        delete_detail = QPushButton("删除")
        delete_detail.clicked.connect(self.delete_selected_document)
        detail_actions.addWidget(delete_detail)
        detail_actions.addStretch()
        detail_layout.addLayout(detail_actions)

        command_panel = QFrame()
        command_panel.setObjectName("softPanel")
        command_layout = QVBoxLayout(command_panel)
        command_layout.setContentsMargins(16, 14, 16, 14)
        command_layout.setSpacing(12)
        command_layout.addWidget(self._panel_heading("自然语言文档指令", ""))
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("例如：把文档中的公司名称加粗，或提取文档结构")
        command_layout.addWidget(self.command_input)
        run_command = QPushButton("执行指令")
        run_command.clicked.connect(self.execute_document_command)
        command_layout.addWidget(run_command, 0, Qt.AlignLeft)
        detail_layout.addWidget(command_panel)

        task_panel = QFrame()
        task_panel.setObjectName("softPanel")
        task_layout = QVBoxLayout(task_panel)
        task_layout.setContentsMargins(16, 14, 16, 14)
        task_layout.setSpacing(12)
        task_layout.addWidget(self._panel_heading("自然语言任务", ""))

        task_config = QGridLayout()
        task_config.setHorizontalSpacing(10)
        task_config.setVerticalSpacing(8)
        self.server_task_url_input = QLineEdit(self.server_task_config.base_url)
        self.server_task_token_input = QLineEdit()
        self.server_task_token_input.setText(self.server_task_config.token)
        self.server_task_token_input.setEchoMode(QLineEdit.Password)
        self.server_task_token_input.setPlaceholderText("Bearer token")
        task_config.addWidget(QLabel("服务器地址"), 0, 0)
        task_config.addWidget(self.server_task_url_input, 0, 1)
        task_config.addWidget(QLabel("Token"), 1, 0)
        task_config.addWidget(self.server_task_token_input, 1, 1)
        task_layout.addLayout(task_config)

        task_config_actions = QHBoxLayout()
        check = QPushButton("检测连接")
        check.setObjectName("secondary")
        check.clicked.connect(self.check_server_task_health)
        task_config_actions.addWidget(check)
        save_config = QPushButton("保存配置")
        save_config.setObjectName("secondary")
        save_config.clicked.connect(self.save_server_task_settings)
        task_config_actions.addWidget(save_config)
        task_config_actions.addStretch()
        task_layout.addLayout(task_config_actions)

        self.server_task_connection_label = QLabel("服务器任务会优先使用当前选中文档；未选中文档时可选择临时文件。")
        self.server_task_connection_label.setObjectName("muted")
        self.server_task_connection_label.setWordWrap(True)
        task_layout.addWidget(self.server_task_connection_label)

        self.server_task_instruction = QPlainTextEdit()
        self.server_task_instruction.setMinimumHeight(82)
        self.server_task_instruction.setPlaceholderText("例如：OCR 后提取金额、日期和供应商，或 convert this file to PDF")
        task_layout.addWidget(self.server_task_instruction)

        file_actions = QHBoxLayout()
        add_files = QPushButton("选择临时文件")
        add_files.setObjectName("secondary")
        add_files.clicked.connect(self.add_server_task_files)
        file_actions.addWidget(add_files)
        clear_files = QPushButton("清空临时文件")
        clear_files.setObjectName("secondary")
        clear_files.clicked.connect(self.clear_server_task_files)
        file_actions.addWidget(clear_files)
        file_actions.addStretch()
        task_layout.addLayout(file_actions)

        self.server_task_files_label = QLabel("输入文件：当前未选择文档，也未选择临时文件")
        self.server_task_files_label.setObjectName("muted")
        self.server_task_files_label.setWordWrap(True)
        task_layout.addWidget(self.server_task_files_label)

        run_actions = QHBoxLayout()
        submit = QPushButton("提交任务")
        submit.clicked.connect(self.submit_server_task)
        run_actions.addWidget(submit)
        refresh = QPushButton("刷新状态")
        refresh.setObjectName("secondary")
        refresh.clicked.connect(self.refresh_server_task_status)
        run_actions.addWidget(refresh)
        download = QPushButton("下载结果")
        download.setObjectName("secondary")
        download.clicked.connect(self.download_server_task_result)
        run_actions.addWidget(download)
        run_actions.addStretch()
        task_layout.addLayout(run_actions)

        self.server_task_status_view = QPlainTextEdit()
        self.server_task_status_view.setReadOnly(True)
        self.server_task_status_view.setMinimumHeight(150)
        self.server_task_status_view.setPlainText("等待提交服务器任务...")
        self.server_task_status_view.setStyleSheet(
            f"background: {INVERSE_ELEVATED}; color: {INVERSE_TEXT}; "
            "border: 1px solid rgba(250,249,245,0.14); border-radius: 8px; "
            "font-family: Consolas; font-size: 13px; padding: 12px;"
        )
        task_layout.addWidget(self.server_task_status_view)
        detail_layout.addWidget(task_panel)
        detail_layout.addStretch()

        splitter.addWidget(table_panel)
        splitter.addWidget(detail_panel)
        splitter.setSizes([760, 360])
        layout.addWidget(splitter)
        return page

    def _fusion_page(self) -> QWidget:
        page, layout = self._page_shell()
        layout.addWidget(
            self._header(
                "融合流程",
                "",
                "刷新实体",
                self.load_entities,
            )
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        grid.addWidget(self._entities_panel(), 0, 0)
        grid.addWidget(self._template_panel(), 0, 1)
        grid.addWidget(self._audit_panel(), 1, 0, 1, 2)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        layout.addLayout(grid)

        fusion_panel = QFrame()
        fusion_panel.setObjectName("paperPanel")
        fusion_layout = QVBoxLayout(fusion_panel)
        fusion_layout.setContentsMargins(20, 18, 20, 20)
        fusion_layout.setSpacing(12)
        fusion_header = QHBoxLayout()
        fusion_header.addWidget(self._panel_heading("跨文档实体关联", ""), 1)
        refresh_fusion = QPushButton("刷新关联")
        refresh_fusion.setObjectName("secondary")
        refresh_fusion.clicked.connect(self.load_cross_document_entities)
        fusion_header.addWidget(refresh_fusion)
        export_fusion = QPushButton("导出融合报告")
        export_fusion.clicked.connect(self.export_fusion_report)
        fusion_header.addWidget(export_fusion)
        fusion_layout.addLayout(fusion_header)
        self.fusion_empty = QLabel("暂无跨文档重复实体。请先导入并抽取多个相关文档。")
        self.fusion_empty.setObjectName("muted")
        self.fusion_empty.setWordWrap(True)
        fusion_layout.addWidget(self.fusion_empty)
        self.fusion_table = QTableWidget(0, 5)
        self.fusion_table.setHorizontalHeaderLabels(["类型", "实体", "文档数", "次数", "关联文档"])
        self.fusion_table.verticalHeader().setVisible(False)
        self.fusion_table.setAlternatingRowColors(True)
        self.fusion_table.horizontalHeader().setStretchLastSection(True)
        self.fusion_table.setMinimumHeight(260)
        fusion_layout.addWidget(self.fusion_table)
        layout.addWidget(fusion_panel)
        return page

    def _entities_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("paperPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(self._panel_heading("实体查询", ""))
        search_row = QHBoxLayout()
        self.entity_keyword = QLineEdit()
        self.entity_keyword.setPlaceholderText("按实体值或上下文搜索")
        search_row.addWidget(self.entity_keyword, 1)
        search = QPushButton("搜索")
        search.setObjectName("secondary")
        search.clicked.connect(self.load_entities)
        search_row.addWidget(search)
        export_csv = QPushButton("导出 CSV")
        export_csv.setObjectName("secondary")
        export_csv.clicked.connect(lambda: self.export_entities("csv"))
        search_row.addWidget(export_csv)
        export_xlsx = QPushButton("导出 Excel")
        export_xlsx.setObjectName("secondary")
        export_xlsx.clicked.connect(lambda: self.export_entities("xlsx"))
        search_row.addWidget(export_xlsx)
        layout.addLayout(search_row)

        self.entities_empty = QLabel("暂无实体。请先解析并抽取文档，或清空搜索关键词后刷新。")
        self.entities_empty.setObjectName("muted")
        self.entities_empty.setWordWrap(True)
        layout.addWidget(self.entities_empty)

        self.entities_table = QTableWidget(0, 4)
        self.entities_table.setHorizontalHeaderLabels(["类型", "值", "置信度", "上下文"])
        self.entities_table.verticalHeader().setVisible(False)
        self.entities_table.setAlternatingRowColors(True)
        self.entities_table.horizontalHeader().setStretchLastSection(True)
        self.entities_table.setMinimumHeight(280)
        layout.addWidget(self.entities_table)
        return panel

    def _template_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("paperPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(self._panel_heading("模板填充", ""))

        upload = QPushButton("上传模板")
        upload.clicked.connect(self.upload_template)
        layout.addWidget(upload)
        fill = QPushButton("用当前实体填充模板")
        fill.setObjectName("secondary")
        fill.clicked.connect(self.fill_template)
        layout.addWidget(fill)
        status = QPushButton("查询填充任务")
        status.setObjectName("secondary")
        status.clicked.connect(self.check_fill_status)
        layout.addWidget(status)

        self.template_status = QLabel("尚未上传模板")
        self.template_status.setObjectName("muted")
        self.template_status.setWordWrap(True)
        layout.addWidget(self.template_status)
        layout.addStretch()
        return panel

    def _audit_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("darkPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 20)
        title = QLabel("操作日志")
        title.setStyleSheet(f"color: {INVERSE_TEXT}; font-size: 16px; font-weight: 650;")
        layout.addWidget(title)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setPlainText("等待操作...")
        self.log_view.setStyleSheet(
            f"background: {INVERSE_ELEVATED}; color: {INVERSE_MUTED}; "
            "border: 1px solid rgba(250,249,245,0.14); border-radius: 8px; "
            "font-family: Consolas; font-size: 13px; padding: 12px;"
        )
        layout.addWidget(self.log_view)
        return panel

    def _articles_page(self) -> QWidget:
        page, layout = self._page_shell()
        layout.addWidget(
            self._header("文章库", "", "刷新文章", self.load_articles)
        )

        crawler_panel = QFrame()
        crawler_panel.setObjectName("paperPanel")
        crawler_layout = QVBoxLayout(crawler_panel)
        crawler_layout.setContentsMargins(20, 18, 20, 20)
        crawler_layout.setSpacing(12)
        crawler_layout.addWidget(self._panel_heading("爬虫获取文章", ""))

        source_row = QHBoxLayout()
        for source in news_sources():
            checkbox = QCheckBox(source)
            checkbox.setChecked(True)
            self.source_checks[source] = checkbox
            source_row.addWidget(checkbox)
        source_row.addStretch()
        crawler_layout.addLayout(source_row)

        control_row = QHBoxLayout()
        control_row.addWidget(QLabel("每源数量"))
        self.crawl_count = QSpinBox()
        self.crawl_count.setRange(1, 50)
        self.crawl_count.setValue(5)
        control_row.addWidget(self.crawl_count)
        self.crawl_button = QPushButton("开始爬取预览")
        self.crawl_button.clicked.connect(self.start_crawl_articles)
        control_row.addWidget(self.crawl_button)
        self.store_crawl_button = QPushButton("入库选中文章")
        self.store_crawl_button.setObjectName("secondary")
        self.store_crawl_button.clicked.connect(self.store_selected_crawled_articles)
        self.store_crawl_button.setEnabled(False)
        control_row.addWidget(self.store_crawl_button)
        self.generate_docs_button = QPushButton("生成测试文档")
        self.generate_docs_button.setObjectName("secondary")
        self.generate_docs_button.clicked.connect(self.generate_crawled_documents)
        self.generate_docs_button.setEnabled(False)
        control_row.addWidget(self.generate_docs_button)
        control_row.addStretch()
        crawler_layout.addLayout(control_row)

        self.crawl_progress = QProgressBar()
        self.crawl_progress.setValue(0)
        crawler_layout.addWidget(self.crawl_progress)
        self.crawl_status = QLabel("就绪")
        self.crawl_status.setObjectName("muted")
        self.crawl_status.setWordWrap(True)
        crawler_layout.addWidget(self.crawl_status)
        self.crawl_preview_empty = QLabel("爬取结果会先显示在下方预览表，确认后再入库。")
        self.crawl_preview_empty.setObjectName("muted")
        self.crawl_preview_empty.setWordWrap(True)
        crawler_layout.addWidget(self.crawl_preview_empty)
        self.crawl_preview_table = QTableWidget(0, 5)
        self.crawl_preview_table.setHorizontalHeaderLabels(["标题", "来源", "作者", "日期", "摘要"])
        self.crawl_preview_table.verticalHeader().setVisible(False)
        self.crawl_preview_table.setAlternatingRowColors(True)
        self.crawl_preview_table.horizontalHeader().setStretchLastSection(True)
        self.crawl_preview_table.setMinimumHeight(180)
        crawler_layout.addWidget(self.crawl_preview_table)
        layout.addWidget(crawler_panel)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)

        list_panel = QFrame()
        list_panel.setObjectName("paperPanel")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(20, 18, 20, 20)
        list_layout.setSpacing(12)
        list_layout.addWidget(self._panel_heading("文章列表", ""))
        self.articles_empty = QLabel("暂无文章。可以先在上方启动爬虫，或刷新已入库文章。")
        self.articles_empty.setObjectName("muted")
        self.articles_empty.setWordWrap(True)
        list_layout.addWidget(self.articles_empty)
        self.articles_table = QTableWidget(0, 5)
        self.articles_table.setHorizontalHeaderLabels(["ID", "标题", "来源", "分类", "抓取时间"])
        self.articles_table.verticalHeader().setVisible(False)
        self.articles_table.setAlternatingRowColors(True)
        self.articles_table.horizontalHeader().setStretchLastSection(True)
        self.articles_table.itemSelectionChanged.connect(self._on_article_selected)
        self.articles_table.setMinimumHeight(360)
        list_layout.addWidget(self.articles_table)

        detail_panel = QFrame()
        detail_panel.setObjectName("paperPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(20, 18, 20, 20)
        detail_layout.setSpacing(12)
        detail_layout.addWidget(self._panel_heading("文章详情", ""))
        self.article_title = QLabel("尚未选择文章")
        self.article_title.setObjectName("sectionTitle")
        detail_layout.addWidget(self.article_title)
        self.article_meta = QLabel("")
        self.article_meta.setObjectName("muted")
        self.article_meta.setWordWrap(True)
        detail_layout.addWidget(self.article_meta)
        self.article_content = QPlainTextEdit()
        self.article_content.setReadOnly(True)
        self.article_content.setPlaceholderText("文章详情会显示在这里")
        self.article_content.setMinimumHeight(320)
        detail_layout.addWidget(self.article_content)

        grid.addWidget(list_panel, 0, 0)
        grid.addWidget(detail_panel, 0, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        layout.addLayout(grid)
        return page

    def _settings_page(self) -> QWidget:
        page, layout = self._page_shell()
        layout.addWidget(
            self._header(
                "系统设置",
                "",
                "检测连接",
                self.check_health,
            )
        )

        overview = QGridLayout()
        overview.setHorizontalSpacing(18)
        overview.setVerticalSpacing(18)

        service_panel = QFrame()
        service_panel.setObjectName("paperPanel")
        service_layout = QVBoxLayout(service_panel)
        service_layout.setContentsMargins(22, 20, 22, 22)
        service_layout.setSpacing(14)
        service_layout.addWidget(self._panel_heading("后端服务", ""))

        status_box = QFrame()
        status_box.setObjectName("softPanel")
        status_layout = QVBoxLayout(status_box)
        status_layout.setContentsMargins(16, 14, 16, 14)
        status_layout.setSpacing(8)
        status_layout.addWidget(Tag("本机连接", TEAL_SOFT, TEAL))
        self.settings_status_text = QLabel("尚未检测。点击检测连接或启动后端服务。")
        self.settings_status_text.setObjectName("muted")
        self.settings_status_text.setWordWrap(True)
        status_layout.addWidget(self.settings_status_text)
        service_layout.addWidget(status_box)

        service_buttons = QHBoxLayout()
        start_backend = QPushButton("启动后端服务")
        start_backend.clicked.connect(self.start_backend_service)
        service_buttons.addWidget(start_backend)
        check_backend = QPushButton("检测连接")
        check_backend.setObjectName("secondary")
        check_backend.clicked.connect(self.check_health)
        service_buttons.addWidget(check_backend)
        service_buttons.addStretch()
        service_layout.addLayout(service_buttons)

        self.backend_pid_label = QLabel("服务进程：未由当前窗口启动")
        self.backend_pid_label.setObjectName("caption")
        service_layout.addWidget(self.backend_pid_label)

        api_panel = QFrame()
        api_panel.setObjectName("paperPanel")
        api_layout = QVBoxLayout(api_panel)
        api_layout.setContentsMargins(22, 20, 22, 22)
        api_layout.setSpacing(14)
        api_layout.addWidget(self._panel_heading("DocFusion 后端 API", ""))

        self.base_url_input = QLineEdit(self.client.base_url)
        api_layout.addWidget(QLabel("API 地址"))
        api_layout.addWidget(self.base_url_input)

        api_actions = QHBoxLayout()
        save = QPushButton("应用地址")
        save.clicked.connect(self.apply_api_url)
        api_actions.addWidget(save)
        reset = QPushButton("恢复默认")
        reset.setObjectName("secondary")
        reset.clicked.connect(self.reset_api_url)
        api_actions.addWidget(reset)
        api_actions.addStretch()
        api_layout.addLayout(api_actions)

        token_path = self.client.project_root / "data" / "api_token.txt"
        token_box = QFrame()
        token_box.setObjectName("softPanel")
        token_layout = QVBoxLayout(token_box)
        token_layout.setContentsMargins(16, 14, 16, 14)
        token_layout.setSpacing(8)
        token_layout.addWidget(Tag("凭据来源", PRIMARY_SOFT, PRIMARY))
        token_label = QLabel(f"DOCFUSION_API_TOKEN 环境变量，或主项目 token 文件：\n{token_path}")
        token_label.setObjectName("muted")
        token_label.setWordWrap(True)
        token_layout.addWidget(token_label)
        api_layout.addWidget(token_box)

        overview.addWidget(service_panel, 0, 0)
        overview.addWidget(api_panel, 0, 1)
        overview.setColumnStretch(0, 1)
        overview.setColumnStretch(1, 1)
        layout.addLayout(overview)

        provider_panel = QFrame()
        provider_panel.setObjectName("paperPanel")
        provider_layout = QVBoxLayout(provider_panel)
        provider_layout.setContentsMargins(22, 18, 22, 20)
        provider_layout.setSpacing(12)
        provider_layout.addWidget(self._panel_heading("模型 Provider API", ""))

        provider_grid = QGridLayout()
        provider_grid.setHorizontalSpacing(16)
        provider_grid.setVerticalSpacing(10)

        self.provider_mode = QComboBox()
        self.provider_mode.addItem("Ollama 本地模型", "ollama")
        self.provider_mode.addItem("OpenAI / 兼容 API", "openai")
        self.provider_mode.setMinimumHeight(42)
        provider_grid.addWidget(QLabel("Provider 类型"), 0, 0)
        self.provider_mode.currentIndexChanged.connect(self._update_provider_field_state)
        provider_grid.addWidget(self.provider_mode, 0, 1)

        self.provider_vendor = QComboBox()
        for vendor_id, label in cloud_vendor_options():
            self.provider_vendor.addItem(label, vendor_id)
        self.provider_vendor.setMinimumHeight(42)
        provider_grid.addWidget(QLabel("云端供应商"), 0, 2)
        self.provider_vendor.currentIndexChanged.connect(lambda _index: self._apply_vendor_defaults(force=True))
        provider_grid.addWidget(self.provider_vendor, 0, 3)

        self.ollama_base_url_input = QLineEdit()
        self.ollama_base_url_input.setPlaceholderText("http://localhost:11434")
        provider_grid.addWidget(QLabel("Ollama Base URL"), 1, 0)
        provider_grid.addWidget(self.ollama_base_url_input, 1, 1)

        self.ollama_model_input = QLineEdit()
        self.ollama_model_input.setPlaceholderText("qwen2.5:7b")
        provider_grid.addWidget(QLabel("Ollama Model"), 1, 2)
        provider_grid.addWidget(self.ollama_model_input, 1, 3)

        self.openai_base_url_input = QLineEdit()
        self.openai_base_url_input.setPlaceholderText("https://api.openai.com/v1")
        provider_grid.addWidget(QLabel("Base URL"), 2, 0)
        provider_grid.addWidget(self.openai_base_url_input, 2, 1, 1, 3)

        self.openai_api_key_input = QLineEdit()
        self.openai_api_key_input.setEchoMode(QLineEdit.Password)
        self.openai_api_key_input.setPlaceholderText("sk-... 或第三方供应商 key")
        provider_grid.addWidget(QLabel("API Key"), 3, 0)
        provider_grid.addWidget(self.openai_api_key_input, 3, 1, 1, 3)

        self.openai_model_input = QLineEdit()
        self.openai_model_input.setPlaceholderText("Model，例如 gpt-4o-mini")
        provider_grid.addWidget(QLabel("Model"), 4, 0)
        provider_grid.addWidget(self.openai_model_input, 4, 1)

        self.openai_proxy_input = QLineEdit()
        self.openai_proxy_input.setPlaceholderText("Proxy，可留空")
        provider_grid.addWidget(QLabel("Proxy"), 4, 2)
        provider_grid.addWidget(self.openai_proxy_input, 4, 3)

        provider_grid_container = QWidget()
        provider_grid_container.setLayout(provider_grid)
        provider_grid_container.setVisible(False)

        provider_form = QGridLayout()
        provider_form.setHorizontalSpacing(14)
        provider_form.setVerticalSpacing(14)

        basic_block = FieldBlock("供应商基础信息")
        basic_block.layout().itemAt(0).widget().hide()
        basic_block.layout().setContentsMargins(14, 12, 14, 14)
        basic_grid = QGridLayout()
        basic_grid.setHorizontalSpacing(12)
        basic_grid.setVerticalSpacing(8)
        basic_grid.addWidget(QLabel("Provider 类型"), 0, 0)
        self.provider_mode_label = basic_grid.itemAtPosition(0, 0).widget()
        basic_grid.addWidget(self.provider_mode, 0, 1)
        basic_grid.addWidget(QLabel("云端供应商"), 1, 0)
        self.provider_vendor_label = basic_grid.itemAtPosition(1, 0).widget()
        self.provider_vendor_label.setText("云端供应商")
        basic_grid.addWidget(self.provider_vendor, 1, 1)
        basic_block.body.addLayout(basic_grid)
        self.provider_mode_label.hide()
        self.provider_vendor_label.hide()
        basic_row = QHBoxLayout()
        basic_row.setSpacing(16)

        mode_field = QVBoxLayout()
        mode_field.setSpacing(6)
        compact_mode_label = QLabel("Provider 类型")
        compact_mode_label.setObjectName("fieldLabel")
        mode_field.addWidget(compact_mode_label)
        compact_mode_label.hide()
        mode_field.addWidget(self.provider_mode)
        basic_row.addLayout(mode_field, 1)

        self.provider_vendor_field = QWidget()
        vendor_field = QVBoxLayout(self.provider_vendor_field)
        vendor_field.setContentsMargins(0, 0, 0, 0)
        vendor_field.setSpacing(6)
        compact_vendor_label = QLabel("云端供应商")
        compact_vendor_label.setObjectName("fieldLabel")
        vendor_field.addWidget(compact_vendor_label)
        compact_vendor_label.hide()
        vendor_field.addWidget(self.provider_vendor)
        basic_row.addWidget(self.provider_vendor_field, 1)
        basic_block.body.addLayout(basic_row)
        self.provider_basic_block = basic_block
        provider_form.addWidget(basic_block, 0, 0, 1, 2)

        ollama_block = FieldBlock("Ollama 本地模型")
        ollama_block.layout().itemAt(0).widget().hide()
        ollama_block.layout().setContentsMargins(14, 12, 14, 14)
        ollama_grid = QGridLayout()
        ollama_grid.setHorizontalSpacing(12)
        ollama_grid.setVerticalSpacing(8)
        ollama_base_label = QLabel("Base URL")
        ollama_base_label.setStyleSheet("background: transparent;")
        ollama_grid.addWidget(ollama_base_label, 0, 0)
        ollama_grid.addWidget(self.ollama_base_url_input, 0, 1)
        ollama_model_label = QLabel("Model")
        ollama_model_label.setStyleSheet("background: transparent;")
        ollama_grid.addWidget(ollama_model_label, 1, 0)
        ollama_grid.addWidget(self.ollama_model_input, 1, 1)
        ollama_block.body.addLayout(ollama_grid)
        self.ollama_provider_block = ollama_block
        provider_form.addWidget(ollama_block, 1, 0, 1, 2)

        endpoint_block = FieldBlock("Endpoint / Base URL")
        endpoint_block.layout().itemAt(0).widget().hide()
        endpoint_block.layout().setContentsMargins(0, 0, 0, 0)
        endpoint_header = QHBoxLayout()
        endpoint_header.addWidget(self.openai_base_url_input, 1)
        self.provider_full_url_check = QCheckBox("完整 URL")
        self.provider_full_url_check.setToolTip("启用后表示这里填写的是完整请求 URL；当前后端仍按 base_url 保存。")
        endpoint_header.addWidget(self.provider_full_url_check)
        endpoint_block.body.addLayout(endpoint_header)
        self.provider_endpoint_hint = QLabel("")
        self.provider_endpoint_hint.setObjectName("muted")
        self.provider_endpoint_hint.setWordWrap(True)
        endpoint_block.body.addWidget(self.provider_endpoint_hint)
        self.provider_endpoint_hint.setVisible(False)
        endpoint_block.setVisible(False)

        key_block = FieldBlock("API Key")
        key_block.layout().itemAt(0).widget().setText("OpenAI " + chr(0x517c) + chr(0x5bb9) + " API")
        key_block.layout().itemAt(0).widget().hide()
        key_block.layout().setContentsMargins(14, 12, 14, 14)
        key_block.body.addWidget(endpoint_block)

        model_proxy_grid = QGridLayout()
        model_proxy_grid.setHorizontalSpacing(12)
        model_proxy_grid.setVerticalSpacing(8)
        model_proxy_grid.addWidget(self.openai_model_input, 0, 0)
        model_proxy_grid.addWidget(self.openai_proxy_input, 0, 1)
        key_block.body.addLayout(model_proxy_grid)

        key_label = QLabel("API Key")
        key_label.setObjectName("fieldLabel")
        key_block.body.addWidget(key_label)
        key_label.hide()
        key_row = QHBoxLayout()
        key_row.addWidget(self.openai_api_key_input, 1)
        self.toggle_api_key_button = QPushButton("显示")
        self.toggle_api_key_button.setObjectName("secondary")
        self.toggle_api_key_button.clicked.connect(self.toggle_provider_api_key_visibility)
        key_row.addWidget(self.toggle_api_key_button)
        clear_key = QPushButton("清空")
        clear_key.setObjectName("secondary")
        clear_key.clicked.connect(self.openai_api_key_input.clear)
        key_row.addWidget(clear_key)
        self.provider_key_link_button = QPushButton("获取 API Key")
        self.provider_key_link_button.setObjectName("secondary")
        self.provider_key_link_button.clicked.connect(self.open_provider_api_key_url)
        key_row.addWidget(self.provider_key_link_button)
        key_block.body.addLayout(key_row)

        endpoint_block.setVisible(True)
        self.openai_provider_block = key_block
        provider_form.addWidget(key_block, 1, 0, 1, 2)

        provider_form.setColumnStretch(0, 1)
        provider_form.setColumnStretch(1, 1)
        provider_layout.addLayout(provider_form)
        self._update_provider_field_state()

        self.provider_status_text = QLabel("")
        self.provider_status_text.setObjectName("muted")
        self.provider_status_text.setWordWrap(True)
        self.provider_status_text.setVisible(False)
        provider_layout.addWidget(self.provider_status_text)

        provider_actions = QHBoxLayout()
        load_provider = QPushButton("加载当前配置")
        load_provider.setObjectName("secondary")
        load_provider.clicked.connect(self.load_provider_settings)
        provider_actions.addWidget(load_provider)
        test_provider = QPushButton("测试连接")
        test_provider.setObjectName("secondary")
        test_provider.clicked.connect(self.test_provider_settings)
        provider_actions.addWidget(test_provider)
        save_provider = QPushButton("保存")
        save_provider.clicked.connect(self.save_provider_settings)
        provider_actions.addWidget(save_provider)
        provider_actions.addStretch()
        provider_layout.addLayout(provider_actions)
        layout.addWidget(provider_panel)

        maintenance = QFrame()
        maintenance.setObjectName("paperPanel")
        maintenance_layout = QVBoxLayout(maintenance)
        maintenance_layout.setContentsMargins(22, 20, 22, 22)
        maintenance_layout.setSpacing(14)
        maintenance_layout.addWidget(self._panel_heading("数据与工作区", ""))

        path_grid = QGridLayout()
        path_grid.setHorizontalSpacing(16)
        path_grid.setVerticalSpacing(10)
        rows = [
            ("主项目", str(self.client.project_root)),
            ("上传目录", str(self.client.project_root / "data" / "uploads")),
            ("爬虫目录", str(self.client.project_root / "data" / "crawled")),
            ("数据库", str(self.client.project_root / "data" / "docfusion.db")),
        ]
        for row, (name, value) in enumerate(rows):
            name_label = QLabel(name)
            name_label.setObjectName("caption")
            path_grid.addWidget(name_label, row, 0)
            value_label = QLabel(value)
            value_label.setObjectName("muted")
            value_label.setWordWrap(True)
            path_grid.addWidget(value_label, row, 1)
        maintenance_layout.addLayout(path_grid)

        maintenance_buttons = QHBoxLayout()
        refresh_all = QPushButton("刷新全部数据")
        refresh_all.clicked.connect(self.refresh_all)
        maintenance_buttons.addWidget(refresh_all)
        open_articles = QPushButton("打开文章库")
        open_articles.setObjectName("secondary")
        open_articles.clicked.connect(lambda: self._activate_nav(3))
        maintenance_buttons.addWidget(open_articles)
        maintenance_buttons.addStretch()
        maintenance_layout.addLayout(maintenance_buttons)
        layout.addWidget(maintenance)
        QTimer.singleShot(0, self.load_provider_settings)
        return page

    def refresh_all(self) -> None:
        self.check_health()
        self.load_statistics()
        self.load_documents()
        self.load_entities()
        self.load_articles()

    def check_health(self) -> None:
        self._run_api("检测后端", self.client.health, self._on_health)

    def load_statistics(self) -> None:
        self._run_api("加载统计", self.client.statistics, self._on_statistics)

    def load_documents(self) -> None:
        self._run_api("加载文档", self.client.documents, self._on_documents)

    def load_entities(self) -> None:
        keyword = self.entity_keyword.text().strip() if hasattr(self, "entity_keyword") else ""
        self._run_api("加载实体", lambda: self.client.entities(keyword=keyword or None), self._on_entities)

    def load_articles(self) -> None:
        self._run_api("加载文章", self.client.articles, self._on_articles)

    def load_cross_document_entities(self) -> None:
        self._run_api("加载跨文档关联", cross_document_entities, self._on_fusion_rows)

    def upload_document(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文档",
            str(Path.home()),
            "Documents (*.docx *.xlsx *.md *.txt *.pdf);;All files (*.*)",
        )
        if path:
            self._run_api("上传文档", lambda: self.client.upload_document(path), lambda data: self._after_mutation(data, "文档上传完成"))

    def batch_extract_documents(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "批量选择文档",
            str(Path.home()),
            "Documents (*.docx *.xlsx *.md *.txt *.pdf *.png *.jpg *.jpeg *.bmp);;All files (*.*)",
        )
        if not paths:
            return
        runnable = ProgressApiRunnable(lambda progress: batch_extract_documents(paths, progress))
        runnable.signals.progress.connect(lambda event: self.log(event.get("message", str(event)) if isinstance(event, dict) else str(event)))
        runnable.signals.succeeded.connect(lambda data: self._after_mutation(data, "批量提取完成"))
        runnable.signals.failed.connect(lambda message: self._on_api_error("批量提取", message))
        self.pool.start(runnable)

    def parse_selected_document(self) -> None:
        doc_id = self._require_selected_doc()
        if doc_id:
            self._run_api("解析文档", lambda: self.client.parse_document(doc_id), lambda data: self._after_mutation(data, "文档解析完成"))

    def extract_selected_document(self) -> None:
        doc_id = self._require_selected_doc()
        if doc_id:
            self._run_api("抽取实体", lambda: self.client.extract_document(doc_id), lambda data: self._after_mutation(data, "实体抽取完成"))

    def reextract_selected_document(self) -> None:
        doc_id = self._require_selected_doc()
        if not doc_id:
            return
        if QMessageBox.question(self, "确认重新提取", f"将清除文档 #{doc_id} 的已有实体并重新提取，是否继续？") != QMessageBox.Yes:
            return
        self._run_api(
            "清除并重新提取",
            lambda: clear_and_reextract_document(doc_id),
            lambda data: self._after_mutation(data, "重新提取完成"),
        )

    def delete_selected_document(self) -> None:
        doc_id = self._require_selected_doc()
        if not doc_id:
            return
        if QMessageBox.question(self, "确认删除", f"确定删除文档 #{doc_id} 吗？") != QMessageBox.Yes:
            return
        self._run_api("删除文档", lambda: self.client.delete_document(doc_id), lambda data: self._after_mutation(data, "文档已删除"))

    def download_selected_document(self) -> None:
        doc = self._selected_document()
        if not doc:
            QMessageBox.information(self, "未选择文档", "请先选择要下载的文档。")
            return
        doc_id = int(doc["id"])
        filename = doc.get("filename") or f"document-{doc_id}.docx"
        default_path = str(Path.home() / "Downloads" / filename)
        target, _ = QFileDialog.getSaveFileName(self, "保存文档", default_path)
        if not target:
            return
        self._run_api(
            "下载文档",
            lambda: self.client.download_document(doc_id, target),
            self._on_document_downloaded,
        )

    def execute_document_command(self) -> None:
        doc_id = self._require_selected_doc()
        if not doc_id:
            return
        command = self.command_input.text().strip()
        if not command:
            QMessageBox.information(self, "缺少指令", "请输入要执行的自然语言文档指令。")
            return
        self._run_api(
            "执行文档指令",
            lambda: self.client.command_document(doc_id, command),
            lambda data: self._after_mutation(data, "文档指令执行完成"),
        )

    def export_entities(self, fmt: str) -> None:
        suffix = "xlsx" if fmt == "xlsx" else "csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出实体",
            str(Path.home() / f"entities.{suffix}"),
            "Excel (*.xlsx)" if suffix == "xlsx" else "CSV (*.csv)",
        )
        if not path:
            return
        keyword = self.entity_keyword.text().strip() if hasattr(self, "entity_keyword") else ""
        doc_id = self.selected_doc_id
        self._run_api(
            "导出实体",
            lambda: self.client.export_entities(path, fmt=fmt, doc_id=doc_id, keyword=keyword or None),
            lambda target: self.log(f"实体已导出：{target}"),
        )

    def upload_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择模板", str(Path.home()), "Templates (*.xlsx *.docx);;All files (*.*)")
        if path:
            self._run_api("上传模板", lambda: self.client.upload_template(path), self._on_template_uploaded)

    def fill_template(self) -> None:
        if not self.latest_template_id:
            QMessageBox.information(self, "缺少模板", "请先上传模板。")
            return
        document_ids = [self.selected_doc_id] if self.selected_doc_id else []
        self._run_api(
            "填充模板",
            lambda: self.client.fill_template(self.latest_template_id, document_ids=document_ids),
            self._on_fill_started,
        )

    def check_fill_status(self) -> None:
        if not self.latest_task_id:
            QMessageBox.information(self, "缺少任务", "还没有可查询的填充任务。")
            return
        self._run_api("查询任务", lambda: self.client.fill_status(self.latest_task_id), self._on_fill_status)

    def check_server_task_health(self) -> None:
        self._run_api("检测服务器任务", self._server_task_client().health, self._on_server_task_health)

    def save_server_task_settings(self) -> None:
        config = ServerTaskConfig(
            base_url=self.server_task_url_input.text().strip(),
            token=self.server_task_token_input.text().strip(),
        )
        save_server_task_config(config, self.server_task_config_path)
        self.server_task_config = config
        self.server_task_connection_label.setText(f"服务器任务配置已保存：{self.server_task_config_path}")
        self.log(f"服务器任务配置已保存：{self.server_task_config_path}")

    def check_server_task_tools(self) -> None:
        self._run_api("检查服务器工具", self._server_task_client().tools, self._on_server_task_tools)

    def add_server_task_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择服务器任务文件",
            str(Path.home()),
            "Documents (*.docx *.xlsx *.pptx *.pdf *.txt *.md *.html *.csv *.jpg *.jpeg *.png *.tiff);;All files (*.*)",
        )
        if not files:
            return
        known = {path.resolve() for path in self.server_task_files}
        for file_name in files:
            path = Path(file_name)
            if path.resolve() not in known:
                self.server_task_files.append(path)
                known.add(path.resolve())
        self._render_server_task_files()

    def clear_server_task_files(self) -> None:
        self.server_task_files.clear()
        self._render_server_task_files()

    def submit_server_task(self) -> None:
        instruction = self.server_task_instruction.toPlainText().strip()
        if not instruction:
            QMessageBox.information(self, "缺少指令", "请先输入自然语言任务指令。")
            return
        task_files = self._server_task_input_files()
        if not task_files:
            QMessageBox.information(self, "缺少文件", "请先在文档库选择文档，或选择临时文件。")
            return
        self._run_api(
            "提交服务器任务",
            lambda: self._server_task_client().submit_instruction(instruction, task_files),
            self._on_server_task_submitted,
        )

    def refresh_server_task_status(self) -> None:
        if not self.latest_server_task_id:
            QMessageBox.information(self, "缺少任务", "还没有可查询的服务器任务。")
            return
        self._run_api(
            "刷新服务器任务",
            lambda: self._server_task_client().task_status(self.latest_server_task_id),
            self._on_server_task_status,
        )

    def download_server_task_result(self) -> None:
        if not self.latest_server_task_id:
            QMessageBox.information(self, "缺少任务", "还没有可下载的服务器任务。")
            return
        directory = QFileDialog.getExistingDirectory(self, "选择下载目录", str(Path.home()))
        if not directory:
            return
        self._run_api(
            "下载服务器任务结果",
            lambda: self._server_task_client().download_result(self.latest_server_task_id, directory),
            lambda path: self._on_server_task_downloaded(Path(path)),
        )

    def load_selected_article_detail(self) -> None:
        if not self.selected_article_id:
            return
        self._run_api(
            "加载文章详情",
            lambda: self.client.article_detail(self.selected_article_id),
            self._on_article_detail,
        )

    def start_crawl_articles(self) -> None:
        sources = [source for source, checkbox in self.source_checks.items() if checkbox.isChecked()]
        if not sources:
            QMessageBox.information(self, "缺少新闻源", "请至少选择一个新闻源。")
            return
        count = self.crawl_count.value()
        self.crawl_button.setEnabled(False)
        self.crawl_button.setText("爬取中...")
        self.store_crawl_button.setEnabled(False)
        self.generate_docs_button.setEnabled(False)
        self.crawl_progress.setRange(0, max(len(sources) * count, 1))
        self.crawl_progress.setValue(0)
        self.crawl_status.setText(f"准备爬取：{', '.join(sources)}")
        self.log(f"开始爬虫任务：sources={sources}, count={count}")

        runnable = ProgressApiRunnable(lambda progress: crawl_articles(sources, count, progress))
        runnable.signals.progress.connect(self._on_crawl_progress)
        runnable.signals.succeeded.connect(self._on_crawl_finished)
        runnable.signals.failed.connect(lambda message: self._on_crawl_failed(message))
        self.pool.start(runnable)

    def store_selected_crawled_articles(self) -> None:
        articles = self._selected_crawled_articles()
        if not articles:
            QMessageBox.information(self, "没有选择", "请先在爬取预览表中选择文章，或全不选以入库全部。")
            return
        self._run_api(
            "入库爬取文章",
            lambda: store_crawled_articles(articles),
            lambda data: self._after_store_crawled(data),
        )

    def generate_crawled_documents(self) -> None:
        articles = self._selected_crawled_articles()
        if not articles:
            QMessageBox.information(self, "没有文章", "请先爬取文章并选择要生成文档的条目。")
            return
        self._run_api(
            "生成测试文档",
            lambda: generate_crawled_documents(articles),
            lambda data: self.log(f"测试文档已生成：{self._pretty(data)}"),
        )

    def export_fusion_report(self) -> None:
        if not self.fusion_rows:
            QMessageBox.information(self, "暂无数据", "请先刷新跨文档实体关联。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出融合报告",
            str(Path.home() / "fusion_report.xlsx"),
            "Excel (*.xlsx)",
        )
        if path:
            self._run_api(
                "导出融合报告",
                lambda: export_fusion_report(path, self.fusion_rows),
                lambda target: self.log(f"融合报告已导出：{target}"),
            )

    def apply_api_url(self) -> None:
        self.client.base_url = self.base_url_input.text().strip().rstrip("/")
        self.log(f"API 地址已切换为 {self.client.base_url}")
        self.refresh_all()

    def reset_api_url(self) -> None:
        self.base_url_input.setText("https://docx.zhuoruan.xyz/api")
        self.apply_api_url()

    def load_provider_settings(self) -> None:
        self._run_api("加载 Provider 配置", load_llm_provider_settings, self._apply_provider_settings_to_form)

    def save_provider_settings(self) -> None:
        config = self._provider_settings_from_form()
        self._run_api(
            "保存配置",
            lambda: save_llm_provider_settings(config),
            self._on_provider_settings_saved,
        )

    def test_provider_settings(self) -> None:
        config = self._provider_settings_from_form()
        self.provider_status_text.setText("正在测试 Provider 连接...")
        self.provider_status_text.setVisible(True)
        self._run_api(
            "测试 Provider 连接",
            lambda: test_llm_provider_settings(config),
            self._on_provider_settings_tested,
        )

    def _apply_provider_settings_to_form(self, data: dict[str, Any]) -> None:
        self._set_combo_value(self.provider_mode, data.get("provider", "ollama"))
        self._set_combo_value(self.provider_vendor, data.get("openai_vendor", "openai"))
        self.ollama_base_url_input.setText(data.get("ollama_url", "http://localhost:11434"))
        self.ollama_model_input.setText(data.get("ollama_model", "qwen2.5:7b"))
        self.openai_base_url_input.setText(data.get("openai_url", "https://api.openai.com/v1"))
        self.openai_api_key_input.setText(data.get("openai_key", ""))
        self.openai_model_input.setText(data.get("openai_model", "gpt-4o-mini"))
        self.openai_proxy_input.setText(data.get("openai_proxy", ""))
        self._update_provider_field_state()
        self._apply_vendor_defaults(force=False)
        self.provider_status_text.setText(
            f"已加载当前 Provider：{self.provider_mode.currentText()} / {data.get('openai_vendor_label', self.provider_vendor.currentText())}"
        )
        self.provider_status_text.setVisible(True)
        self.log("Provider 配置已加载")

    def _provider_settings_from_form(self) -> dict[str, str]:
        return {
            "provider": self.provider_mode.currentData() or "ollama",
            "ollama_url": self.ollama_base_url_input.text().strip(),
            "ollama_model": self.ollama_model_input.text().strip(),
            "openai_vendor": self.provider_vendor.currentData() or "openai",
            "openai_key": self.openai_api_key_input.text().strip(),
            "openai_url": self.openai_base_url_input.text().strip(),
            "openai_proxy": self.openai_proxy_input.text().strip(),
            "openai_model": self.openai_model_input.text().strip(),
        }

    def _on_provider_settings_saved(self, data: dict[str, Any]) -> None:
        self._apply_provider_settings_to_form(data)
        self.provider_status_text.setText("Provider 配置已保存。")
        self.provider_status_text.setVisible(True)
        self.log("Provider 配置已保存")

    def _on_provider_settings_tested(self, data: dict[str, Any]) -> None:
        models = data.get("models") or []
        model_text = "；可用模型：" + "、".join(models[:5]) if models else ""
        status = "连接正常" if data.get("ok") else "连接异常"
        self.provider_status_text.setText(f"{status}：{data.get('message', '')}{model_text}")
        self.provider_status_text.setVisible(True)
        self.log(f"Provider 测试结果：{self._pretty(data)}")

    def toggle_provider_api_key_visibility(self) -> None:
        is_hidden = self.openai_api_key_input.echoMode() == QLineEdit.Password
        self.openai_api_key_input.setEchoMode(QLineEdit.Normal if is_hidden else QLineEdit.Password)
        self.toggle_api_key_button.setText("隐藏" if is_hidden else "显示")

    def open_provider_api_key_url(self) -> None:
        urls = {
            "openai": "https://platform.openai.com/api-keys",
            "deepseek": "https://platform.deepseek.com/api_keys",
            "moonshot": "https://platform.moonshot.cn/console/api-keys",
            "qwen": "https://bailian.console.aliyun.com/",
            "zhipu": "https://open.bigmodel.cn/usercenter/apikeys",
        }
        vendor = self.provider_vendor.currentData() or "openai"
        url = urls.get(vendor)
        if not url:
            QMessageBox.information(self, "获取 API Key", "当前供应商没有内置获取链接，请打开供应商控制台创建 API Key。")
            return
        QDesktopServices.openUrl(QUrl(url))

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _update_provider_field_state(self) -> None:
        is_ollama = (self.provider_mode.currentData() or "ollama") == "ollama"
        for widget in (self.ollama_base_url_input, self.ollama_model_input):
            widget.setEnabled(is_ollama)
        for widget in (
            self.provider_vendor,
            self.openai_base_url_input,
            self.openai_api_key_input,
            self.openai_model_input,
            self.openai_proxy_input,
        ):
            widget.setEnabled(not is_ollama)
        if hasattr(self, "provider_vendor_label"):
            self.provider_vendor_label.setVisible(not is_ollama)
        if hasattr(self, "provider_vendor"):
            self.provider_vendor.setVisible(not is_ollama)
        if hasattr(self, "provider_vendor_field"):
            self.provider_vendor_field.setVisible(not is_ollama)
        if hasattr(self, "provider_full_url_check"):
            self.provider_full_url_check.setEnabled(not is_ollama)
        if hasattr(self, "toggle_api_key_button"):
            self.toggle_api_key_button.setEnabled(not is_ollama)
        if hasattr(self, "provider_key_link_button"):
            self.provider_key_link_button.setEnabled(not is_ollama)
        if hasattr(self, "ollama_provider_block"):
            self.ollama_provider_block.setVisible(is_ollama)
        if hasattr(self, "openai_provider_block"):
            self.openai_provider_block.setVisible(not is_ollama)
        if hasattr(self, "provider_status_text"):
            mode = "Ollama 本地模型" if is_ollama else "OpenAI / 兼容 API"
            self.provider_status_text.setText(f"当前编辑模式：{mode}。保存后会被后端 LLM 工作流读取。")
            self.provider_status_text.setVisible(False)

    def _apply_vendor_defaults(self, force: bool = False) -> None:
        vendor = self.provider_vendor.currentData()
        if not vendor:
            return
        try:
            from llm.provider_presets import get_cloud_vendor_preset
        except Exception:
            return
        preset = get_cloud_vendor_preset(vendor)
        current_url = self.openai_base_url_input.text().strip()
        current_model = self.openai_model_input.text().strip()
        if force or not current_url or current_url == "https://api.openai.com/v1":
            self.openai_base_url_input.setText(preset.get("base_url", ""))
        if force or not current_model or current_model == "gpt-4o-mini":
            self.openai_model_input.setText(preset.get("model_placeholder", ""))
        if hasattr(self, "provider_endpoint_hint"):
            base_url = preset.get("base_url") or "请填写供应商提供的 OpenAI 兼容 Base URL"
            model = preset.get("model_placeholder") or "your-model-name"
            self.provider_endpoint_hint.setText("")
            self.provider_endpoint_hint.setVisible(False)

    def start_backend_service(self) -> None:
        if self.api_process and self.api_process.poll() is None:
            self.log("后端服务已经在当前 UI 会话中启动。")
            self.refresh_all()
            return
        backend_dir = self.client.project_root
        if not (backend_dir / "api" / "server.py").exists():
            QMessageBox.warning(self, "找不到后端", f"未找到后端入口：{backend_dir}")
            return
        self.api_process = subprocess.Popen(
            [sys.executable, "-m", "api.server"],
            cwd=str(backend_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
        )
        self.log(f"正在启动后端服务，PID={self.api_process.pid}")
        if hasattr(self, "backend_pid_label"):
            self.backend_pid_label.setText(f"服务进程：PID {self.api_process.pid}")
        if hasattr(self, "settings_status_text"):
            self.settings_status_text.setText("后端服务正在启动，稍后会自动检测连接。")
        QTimer.singleShot(1800, self.refresh_all)

    def closeEvent(self, event) -> None:
        if self.api_process and self.api_process.poll() is None:
            self.api_process.terminate()
        super().closeEvent(event)

    def _run_api(self, label: str, task: Callable[[], object], on_success: Callable[[Any], None]) -> None:
        self.log(f"{label}...")
        runnable = ApiRunnable(task)
        runnable.signals.succeeded.connect(on_success)
        runnable.signals.failed.connect(lambda message, action=label: self._on_api_error(action, message))
        self.pool.start(runnable)

    def _on_health(self, data: dict[str, Any]) -> None:
        self.api_status_tag.setText("后端已连接")
        self.api_status_tag.setStyleSheet(
            f"background: {TEAL_SOFT}; color: {TEAL}; border-radius: 6px; padding: 4px 8px; font-size: 12px; font-weight: 650;"
        )
        self.api_status_text.setText("FastAPI /api/health 返回正常。")
        if hasattr(self, "settings_status_text"):
            self.settings_status_text.setText(f"连接正常：{self.client.base_url}/health 返回 {data}")
        self.log(f"健康检查：{data}")

    def _on_statistics(self, data: dict[str, Any]) -> None:
        self.metric_docs.set_data(data.get("documents", 0), "来自 /api/statistics")
        self.metric_entities.set_data(data.get("entities", 0), "已抽取结构化实体")
        self.metric_templates.set_data(data.get("templates", 0), "可用于自动填充")
        self.metric_articles.set_data(data.get("articles", 0), "爬取文章记录")
        self.api_preview.setPlainText(self._pretty(data))

    def _on_documents(self, docs: list[dict[str, Any]]) -> None:
        self.documents = docs
        self.documents_table.setRowCount(len(docs))
        if hasattr(self, "documents_empty"):
            self.documents_empty.setVisible(not docs)
        for row, doc in enumerate(docs):
            values = [
                doc.get("id", ""),
                doc.get("filename", ""),
                doc.get("file_type", ""),
                "已解析" if doc.get("parsed") else "未解析",
                doc.get("created_at", "") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setForeground(QColor(INK if col == 1 else BODY))
                self.documents_table.setItem(row, col, item)
        self.documents_table.resizeColumnsToContents()
        self._render_recent_documents()
        self.log(f"文档列表已更新：{len(docs)} 条")

    def _on_entities(self, entities: list[dict[str, Any]]) -> None:
        self.entities = entities
        self.entities_table.setRowCount(len(entities))
        if hasattr(self, "entities_empty"):
            self.entities_empty.setVisible(not entities)
        for row, entity in enumerate(entities):
            values = [
                entity.get("type", ""),
                entity.get("value", ""),
                entity.get("confidence", ""),
                entity.get("context", "") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setForeground(QColor(INK if col == 1 else BODY))
                self.entities_table.setItem(row, col, item)
        self.entities_table.resizeColumnsToContents()
        self.log(f"实体列表已更新：{len(entities)} 条")

    def _on_articles(self, articles: list[dict[str, Any]]) -> None:
        self.articles = articles
        self.articles_table.setRowCount(len(articles))
        if hasattr(self, "articles_empty"):
            self.articles_empty.setVisible(not articles)
        for row, article in enumerate(articles):
            values = [
                article.get("id", ""),
                article.get("title", ""),
                article.get("source", ""),
                article.get("category", ""),
                article.get("crawled_at", "") or article.get("publish_date", "") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setForeground(QColor(INK if col == 1 else BODY))
                self.articles_table.setItem(row, col, item)
        self.articles_table.resizeColumnsToContents()
        self._render_recent_articles()
        self.log(f"文章列表已更新：{len(articles)} 条")

    def _on_article_detail(self, article: dict[str, Any]) -> None:
        self.article_title.setText(article.get("title", "未命名文章"))
        self.article_meta.setText(
            f"来源：{article.get('source') or '-'} | 作者：{article.get('author') or '-'} | "
            f"发布时间：{article.get('publish_date') or '-'} | 分类：{article.get('category') or '-'}\n"
            f"URL：{article.get('url') or '-'}"
        )
        self.article_content.setPlainText(article.get("content") or "")
        self.log(f"文章详情已加载：#{article.get('id')} {article.get('title')}")

    def _on_fusion_rows(self, rows: list[dict[str, Any]]) -> None:
        self.fusion_rows = rows
        self.fusion_table.setRowCount(len(rows))
        if hasattr(self, "fusion_empty"):
            self.fusion_empty.setVisible(not rows)
        for row, item in enumerate(rows):
            values = [
                item.get("type", ""),
                item.get("value", ""),
                item.get("doc_count", ""),
                item.get("count", ""),
                "、".join(item.get("documents") or []),
            ]
            for col, value in enumerate(values):
                table_item = QTableWidgetItem(str(value))
                table_item.setForeground(QColor(INK if col == 1 else BODY))
                self.fusion_table.setItem(row, col, table_item)
        self.fusion_table.resizeColumnsToContents()
        self.log(f"跨文档实体关联已更新：{len(rows)} 条")

    def _on_crawl_progress(self, event: dict[str, Any]) -> None:
        current = int(event.get("current") or 0)
        total = int(event.get("total") or self.crawl_progress.maximum() or 1)
        source = event.get("source") or ""
        message = event.get("message") or ""
        if total > 0:
            self.crawl_progress.setMaximum(max(total, self.crawl_progress.maximum()))
        self.crawl_progress.setValue(min(current, self.crawl_progress.maximum()))
        status = f"{source}: {current}/{total}"
        if message:
            status = f"{status} - {message}"
            self.log(message)
        self.crawl_status.setText(status)

    def _on_crawl_finished(self, result: dict[str, Any]) -> None:
        self.crawl_button.setEnabled(True)
        self.crawl_button.setText("开始爬取预览")
        self.crawl_progress.setValue(self.crawl_progress.maximum())
        self.crawled_preview = result.get("articles", [])
        self._render_crawl_preview()
        self.store_crawl_button.setEnabled(bool(self.crawled_preview))
        self.generate_docs_button.setEnabled(bool(self.crawled_preview))
        self.crawl_status.setText(f"爬取完成：获取 {result.get('fetched', 0)} 篇，等待确认入库")
        self.log(f"爬虫完成：{self._pretty(result)}")

    def _on_crawl_failed(self, message: str) -> None:
        self.crawl_button.setEnabled(True)
        self.crawl_button.setText("开始爬取预览")
        self.crawl_status.setText(f"爬取失败：{message}")
        self.log(f"爬取失败：{message}")

    def _render_crawl_preview(self) -> None:
        self.crawl_preview_table.setRowCount(len(self.crawled_preview))
        self.crawl_preview_empty.setVisible(not self.crawled_preview)
        for row, article in enumerate(self.crawled_preview):
            content = article.get("content", "") or ""
            values = [
                article.get("title", ""),
                article.get("source", ""),
                article.get("author", ""),
                article.get("publish_date", ""),
                content[:100] + ("..." if len(content) > 100 else ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setForeground(QColor(INK if col == 0 else BODY))
                self.crawl_preview_table.setItem(row, col, item)
        self.crawl_preview_table.resizeColumnsToContents()

    def _selected_crawled_articles(self) -> list[dict[str, Any]]:
        if not self.crawled_preview:
            return []
        selected_rows = sorted({index.row() for index in self.crawl_preview_table.selectedIndexes()})
        if not selected_rows:
            return list(self.crawled_preview)
        return [self.crawled_preview[row] for row in selected_rows if 0 <= row < len(self.crawled_preview)]

    def _after_store_crawled(self, data: Any) -> None:
        self.log(f"爬取文章已入库：{self._pretty(data)}")
        self.load_articles()
        self.load_statistics()

    def _render_recent_documents(self) -> None:
        if not hasattr(self, "recent_docs_list"):
            return
        self._clear_layout(self.recent_docs_list)
        if not self.documents:
            self.recent_docs_list.addWidget(self._empty_label("暂无文档，先上传或从爬虫导入文章。"))
            return
        for doc in self.documents[:5]:
            status = "已解析" if doc.get("parsed") else "未解析"
            self.recent_docs_list.addWidget(
                self._summary_row(
                    doc.get("filename", "未命名文档"),
                    f"#{doc.get('id')} · {doc.get('file_type')} · {status}",
                    TEAL if doc.get("parsed") else AMBER,
                )
            )

    def _render_recent_articles(self) -> None:
        if not hasattr(self, "recent_articles_list"):
            return
        self._clear_layout(self.recent_articles_list)
        if not self.articles:
            self.recent_articles_list.addWidget(self._empty_label("暂无文章，可在文章库启动爬虫获取。"))
            return
        for article in self.articles[:5]:
            self.recent_articles_list.addWidget(
                self._summary_row(
                    article.get("title", "未命名文章"),
                    f"{article.get('source') or '-'} · {article.get('category') or '-'}",
                    BLUE,
                )
            )

    def _summary_row(self, title: str, subtitle: str, marker_color: str) -> QFrame:
        row = QFrame()
        row.setObjectName("softPanel")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        marker = QLabel()
        marker.setFixedSize(8, 8)
        marker.setStyleSheet(f"background: {marker_color}; border-radius: 4px;")
        layout.addWidget(marker)
        text = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        title_label.setWordWrap(True)
        text.addWidget(title_label)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("caption")
        subtitle_label.setWordWrap(True)
        text.addWidget(subtitle_label)
        layout.addLayout(text, 1)
        return row

    def _empty_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _after_mutation(self, data: Any, message: str) -> None:
        self.log(f"{message}: {self._pretty(data)}")
        self.load_statistics()
        self.load_documents()
        self.load_entities()

    def _on_template_uploaded(self, data: dict[str, Any]) -> None:
        self.latest_template_id = int(data["id"])
        fields = data.get("fields", [])
        self.template_status.setText(f"模板 #{self.latest_template_id} 已上传：{data.get('filename')}，识别字段 {len(fields)} 个")
        self.log(f"模板上传完成：{self._pretty(data)}")
        self.load_statistics()

    def _on_fill_started(self, data: dict[str, Any]) -> None:
        self.latest_task_id = int(data["task_id"])
        self.template_status.setText(f"填充任务 #{self.latest_task_id} 已创建，状态：{data.get('status')}")
        self.log(f"填充任务已创建：{self._pretty(data)}")

    def _on_fill_status(self, data: dict[str, Any]) -> None:
        self.template_status.setText(
            f"任务 #{data.get('task_id')}：{data.get('status')}，准确率：{data.get('accuracy')}，输出：{data.get('result_path')}"
        )
        self.log(f"填充任务状态：{self._pretty(data)}")

    def _on_server_task_health(self, data: dict[str, Any]) -> None:
        self.server_task_connection_label.setText(f"连接正常：{data}")
        self.log(f"服务器任务健康检查：{self._pretty(data)}")

    def _on_server_task_tools(self, data: dict[str, Any]) -> None:
        self.server_task_connection_label.setText("服务器工具检查完成")
        self.server_task_status_view.setPlainText(self._pretty(data))
        self.log(f"服务器工具检查：{self._pretty(data)}")

    def _on_server_task_submitted(self, data: dict[str, Any]) -> None:
        self.latest_server_task_id = str(data.get("task_id") or "")
        self.server_task_poll_count = 0
        self._on_server_task_status(data)

    def _on_server_task_status(self, data: dict[str, Any]) -> None:
        self.latest_server_task_id = str(data.get("task_id") or self.latest_server_task_id or "")
        self.server_task_status_view.setPlainText(self._pretty(data))
        status = data.get("status")
        self.log(f"服务器任务 {self.latest_server_task_id or '-'}：{status}")
        if status in {"queued", "running"}:
            self._schedule_server_task_poll()
        else:
            self.server_task_poll_count = 0

    def _schedule_server_task_poll(self) -> None:
        if not self.latest_server_task_id:
            return
        self.server_task_poll_count += 1
        if self.server_task_poll_count > self.server_task_max_polls:
            message = f"服务器任务 {self.latest_server_task_id} 轮询已停止：超过 {self.server_task_max_polls} 次仍未完成。"
            self.server_task_status_view.appendPlainText(f"\n{message}")
            self.log(message)
            return
        QTimer.singleShot(1500, self.refresh_server_task_status)

    def _on_server_task_downloaded(self, path: Path) -> None:
        self.server_task_status_view.appendPlainText(f"\nDownloaded: {path}")
        self.log(f"服务器任务结果已下载：{path}")

    def _on_document_downloaded(self, path: Path) -> None:
        self.log(f"文档已下载：{path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _server_task_client(self) -> ServerTaskClient:
        return ServerTaskClient(
            self.server_task_url_input.text().strip(),
            self.server_task_token_input.text().strip(),
        )

    def _render_server_task_files(self) -> None:
        if not hasattr(self, "server_task_files_label"):
            return
        selected_doc = self._selected_document()
        if selected_doc:
            file_path = selected_doc.get("file_path") or selected_doc.get("path")
            self.server_task_files_label.setText(f"输入文件：当前文档\n{file_path or selected_doc.get('filename')}")
            return
        if self.server_task_files:
            self.server_task_files_label.setText("输入文件：临时文件\n" + "\n".join(str(path) for path in self.server_task_files))
            return
        self.server_task_files_label.setText("输入文件：当前未选择文档，也未选择临时文件")

    def _selected_document(self) -> dict[str, Any] | None:
        if self.selected_doc_id is None:
            return None
        for doc in self.documents:
            if int(doc.get("id", -1)) == self.selected_doc_id:
                return doc
        return None

    def _server_task_input_files(self) -> list[Path]:
        selected_doc = self._selected_document()
        if selected_doc:
            raw_path = selected_doc.get("file_path") or selected_doc.get("path")
            if raw_path:
                path = Path(str(raw_path))
                if path.is_file():
                    return [path]
                self.log(f"选中文档文件不存在，改用临时文件：{path}")
        return list(self.server_task_files)

    def _on_api_error(self, action: str, message: str) -> None:
        self.api_status_tag.setText("后端未就绪")
        self.api_status_tag.setStyleSheet(
            f"background: {AMBER_SOFT}; color: {AMBER}; border-radius: 6px; padding: 4px 8px; font-size: 12px; font-weight: 650;"
        )
        self.api_status_text.setText(message)
        if hasattr(self, "settings_status_text"):
            self.settings_status_text.setText(f"{action}失败：{message}")
        self.log(f"{action}失败：{message}")

    def _on_document_selected(self) -> None:
        row = self.documents_table.currentRow()
        if row < 0 or row >= len(self.documents):
            self.selected_doc_id = None
            self.selected_doc_label.setText("尚未选择文档")
            if hasattr(self, "doc_detail_title"):
                self.doc_detail_title.setText("尚未选择文档")
                self.doc_detail_meta.setText("从左侧表格选择文档。")
            self._render_server_task_files()
            return
        doc = self.documents[row]
        self.selected_doc_id = int(doc["id"])
        self.selected_doc_label.setText(
            f"#{doc.get('id')} {doc.get('filename')}，类型 {doc.get('file_type')}，"
            f"{'已解析' if doc.get('parsed') else '未解析'}"
        )
        if hasattr(self, "doc_detail_title"):
            self.doc_detail_title.setText(doc.get("filename", "未命名文档"))
            self.doc_detail_meta.setText(
                f"文档 ID：{doc.get('id')}\n"
                f"文件类型：{doc.get('file_type') or '-'}\n"
                f"解析状态：{'已解析' if doc.get('parsed') else '未解析'}\n"
                f"创建时间：{doc.get('created_at') or '-'}"
            )
        self._render_server_task_files()

    def _on_article_selected(self) -> None:
        row = self.articles_table.currentRow()
        if row < 0 or row >= len(self.articles):
            self.selected_article_id = None
            self.article_title.setText("尚未选择文章")
            self.article_meta.setText("")
            self.article_content.clear()
            return
        article = self.articles[row]
        self.selected_article_id = int(article["id"])
        self.article_title.setText(article.get("title", "加载中..."))
        self.article_meta.setText("正在加载完整内容...")
        self.article_content.clear()
        self.load_selected_article_detail()

    def _require_selected_doc(self) -> int | None:
        if self.selected_doc_id is None:
            QMessageBox.information(self, "需要选择文档", "请先在文档库选择一行。")
            return None
        return self.selected_doc_id

    def _panel_heading(self, title: str, desc: str) -> QWidget:
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        if desc:
            desc_label = QLabel(desc)
            desc_label.setObjectName("muted")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        return box

    def log(self, message: str) -> None:
        if hasattr(self, "log_view"):
            first_block = self.log_view.document().firstBlock()
            if self.log_view.document().blockCount() == 1 and first_block.text().endswith("..."):
                self.log_view.clear()
            self.log_view.appendPlainText(str(message))
            self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    @staticmethod
    def _pretty(data: Any) -> str:
        import json

        return json.dumps(data, ensure_ascii=False, indent=2)
