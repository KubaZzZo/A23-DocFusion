"""文档智能操作面板"""
import asyncio
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLineEdit, QLabel, QFileDialog, QListWidget, QSplitter, QMessageBox,
    QGroupBox, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt
from core.doc_commander import DocCommander
from core.document_workflow import DocumentWorkflow
from core.document_parser import DocumentParser
from db.database import DocumentDAO
from ui.components import mark_secondary
from ui.task_runner import TaskWorker
from logger import get_logger

log = get_logger("ui.doc_panel")


class DocPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.current_doc = None
        self.commander = DocCommander()
        self.document_workflow = DocumentWorkflow()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 上方：文件选择 + 元信息
        file_bar = QHBoxLayout()
        self.btn_open = QPushButton("打开文档")
        mark_secondary(self.btn_open)
        self.btn_open.clicked.connect(self._open_file)
        self.lbl_file = QLabel("未选择文件")
        self.lbl_file.setStyleSheet("color: #888; background: transparent; padding: 0 8px;")
        file_bar.addWidget(self.btn_open)
        file_bar.addWidget(self.lbl_file, 1)

        self.lbl_doc_info = QLabel("")
        self.lbl_doc_info.setStyleSheet("color: #AAA; font-size: 11px; background: transparent;")
        file_bar.addWidget(self.lbl_doc_info)
        layout.addLayout(file_bar)

        # 中间：文档预览 + 操作日志（QGroupBox 包裹）
        splitter = QSplitter(Qt.Orientation.Horizontal)

        preview_group = QGroupBox("文档预览")
        preview_layout = QVBoxLayout(preview_group)
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setPlaceholderText("请点击「打开文档」选择一个文档文件...")
        preview_layout.addWidget(self.txt_preview)
        splitter.addWidget(preview_group)

        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout(log_group)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("执行指令后，操作日志将显示在这里...")
        log_layout.addWidget(self.txt_log)
        splitter.addWidget(log_group)

        splitter.setSizes([600, 400])
        layout.addWidget(splitter, 1)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # 下方：指令输入
        cmd_bar = QHBoxLayout()
        self.input_cmd = QLineEdit()
        self.input_cmd.setPlaceholderText("输入自然语言指令，如：把第二段加粗、查找替换'公司'为'企业'...")
        self.input_cmd.returnPressed.connect(self._execute_command)
        self.btn_exec = QPushButton("执行")
        self.btn_exec.clicked.connect(self._execute_command)
        cmd_bar.addWidget(self.input_cmd, 1)
        cmd_bar.addWidget(self.btn_exec)
        layout.addLayout(cmd_bar)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择文档", "",
                                               "文档文件 (*.docx *.md *.xlsx *.txt *.pdf *.png *.jpg *.jpeg *.bmp)")
        if not path:
            return

        try:
            uploaded = self.document_workflow.upload_document(Path(path).name, Path(path).read_bytes())
            result = self.document_workflow.parse_document(uploaded["id"], include_text=True)
        except Exception as e:
            QMessageBox.critical(self, "解析失败", str(e))
            self._log(f"解析失败: {Path(path).name} - {e}")
            return
        doc = DocumentDAO.get_by_id(uploaded["id"])
        text = result["text"]

        self.current_doc = doc
        self.lbl_file.setText(f"{doc.filename}")
        char_count = len(text)
        line_count = text.count("\n") + 1
        self.lbl_doc_info.setText(f"ID:{doc.id}  |  {doc.file_type.upper()}  |  {char_count} 字  |  {line_count} 行")
        self.txt_preview.setPlainText(text)
        self._log(f"已加载文档: {doc.filename}")

    def _execute_command(self):
        cmd = self.input_cmd.text().strip()
        if not cmd:
            return
        if not self.current_doc:
            QMessageBox.warning(self, "提示", "请先打开一个文档")
            return

        self.btn_exec.setEnabled(False)
        self.btn_exec.setText("执行中...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        doc_info = f"文件名: {self.current_doc.filename}, 类型: {self.current_doc.file_type}"

        self.worker = TaskWorker(
            lambda: self._run_command_task(self.current_doc.file_path, doc_info, cmd),
            error_prefix="document command",
        )
        self.worker.succeeded.connect(self._on_command_done)
        self.worker.failed.connect(self._on_command_error)
        self.worker.start()

    def _run_command_task(self, doc_path: str, doc_info: str, command_text: str) -> dict:
        loop = asyncio.new_event_loop()
        try:
            parsed = loop.run_until_complete(self.commander.parse_command(command_text, doc_info))
            if "error" in parsed:
                raise RuntimeError(parsed["error"])
            result = self.commander.execute(doc_path, parsed)
            result["parsed_command"] = parsed
            return result
        finally:
            loop.close()

    def _on_command_done(self, result):
        self.btn_exec.setEnabled(True)
        self.btn_exec.setText("执行")
        self.progress.setVisible(False)
        parsed = result.get("parsed_command", {})
        self._log(f"指令: {self.input_cmd.text()}")
        self._log(f"解析: {parsed.get('description', '')}")
        self._log(f"结果: {result.get('message', result.get('data', ''))}")
        self._log("---")
        self.input_cmd.clear()

        # 刷新预览
        if self.current_doc:
            try:
                r = DocumentParser.parse(self.current_doc.file_path)
                self.txt_preview.setPlainText(r["text"])
            except Exception as e:
                log.warning(f"刷新预览失败: {e}")

    def _on_command_error(self, msg):
        self.btn_exec.setEnabled(True)
        self.btn_exec.setText("执行")
        self.progress.setVisible(False)
        self._log(f"错误: {msg}")

    def _log(self, text):
        self.txt_log.append(text)
