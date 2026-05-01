"""信息提取面板 - 文档解析 + 实体提取"""
import asyncio
import csv
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QFileDialog, QTableWidget, QTableWidgetItem, QSplitter,
    QProgressBar, QMessageBox, QHeaderView, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from core.document_workflow import DocumentWorkflow
from core.entity_extractor import EntityExtractor
from db.database import DocumentDAO, EntityDAO
from ui.task_runner import ProgressTaskWorker, TaskWorker

# 实体类型颜色映射
ENTITY_COLORS = {
    "person":       ("#5B8DEF", "#EBF1FF", "人名"),
    "organization": ("#52C41A", "#EFFFEB", "机构"),
    "date":         ("#FAAD14", "#FFF8E6", "日期"),
    "amount":       ("#FF4D4F", "#FFF1F0", "金额"),
    "phone":        ("#722ED1", "#F5EDFF", "电话"),
    "email":        ("#13C2C2", "#E8FFFE", "邮箱"),
    "address":      ("#EB2F96", "#FFF0F6", "地址"),
    "id_number":    ("#FA8C16", "#FFF4E6", "编号"),
    "custom":       ("#8C8C8C", "#F5F5F5", "其他"),
}


def _type_badge(entity_type: str) -> QLabel:
    """创建实体类型彩色标签"""
    fg, bg, cn_name = ENTITY_COLORS.get(entity_type, ("#8C8C8C", "#F5F5F5", entity_type))
    lbl = QLabel(cn_name)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(f"""
        background: {bg}; color: {fg}; font-size: 11px; font-weight: bold;
        border-radius: 4px; padding: 2px 8px;
    """)
    return lbl


class ExtractPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.current_doc = None
        self.current_entities = []
        self.document_workflow = DocumentWorkflow()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 文件选择栏
        file_bar = QHBoxLayout()
        self.btn_open = QPushButton("选择文档")
        self.btn_open.clicked.connect(self._open_file)
        self.btn_batch = QPushButton("批量提取")
        self.btn_batch.clicked.connect(self._open_batch_files)
        self.lbl_file = QLabel("未选择文件")
        self.lbl_file.setStyleSheet("color: #888; background: transparent; padding: 0 8px;")
        file_bar.addWidget(self.btn_open)
        file_bar.addWidget(self.btn_batch)
        file_bar.addWidget(self.lbl_file, 1)

        # 文档信息标签
        self.lbl_doc_info = QLabel("")
        self.lbl_doc_info.setStyleSheet("color: #AAA; font-size: 11px; background: transparent;")
        file_bar.addWidget(self.lbl_doc_info)
        layout.addLayout(file_bar)

        # 中间区域
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：文档文本
        left = QGroupBox("文档内容")
        left_layout = QVBoxLayout(left)
        self.txt_content = QTextEdit()
        self.txt_content.setReadOnly(True)
        self.txt_content.setPlaceholderText("选择文档后显示解析内容...")
        left_layout.addWidget(self.txt_content)
        splitter.addWidget(left)

        # 右侧：提取结果
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.btn_extract = QPushButton("提取实体信息")
        self.btn_extract.clicked.connect(self._start_extract)
        self.btn_extract.setEnabled(False)
        action_bar = QHBoxLayout()
        action_bar.addWidget(self.btn_extract)
        self.btn_reextract = QPushButton("清除并重新提取")
        self.btn_reextract.clicked.connect(self._clear_and_reextract)
        self.btn_reextract.setEnabled(False)
        action_bar.addWidget(self.btn_reextract)
        self.btn_export_csv = QPushButton("导出CSV")
        self.btn_export_csv.clicked.connect(lambda: self._export_entities("csv"))
        self.btn_export_csv.setEnabled(False)
        action_bar.addWidget(self.btn_export_csv)
        self.btn_export_xlsx = QPushButton("导出Excel")
        self.btn_export_xlsx.clicked.connect(lambda: self._export_entities("xlsx"))
        self.btn_export_xlsx.setEnabled(False)
        action_bar.addWidget(self.btn_export_xlsx)
        right_layout.addLayout(action_bar)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        right_layout.addWidget(self.progress)

        # 摘要卡片
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("""
            QFrame {
                background: #F0F5FF;
                border: 1px solid #D6E4FF;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        self.summary_frame.setVisible(False)
        summary_layout = QVBoxLayout(self.summary_frame)
        summary_layout.setContentsMargins(12, 8, 12, 8)
        summary_layout.setSpacing(4)
        self.lbl_topic = QLabel("")
        self.lbl_topic.setStyleSheet("font-size: 13px; font-weight: bold; color: #5B8DEF; background: transparent;")
        summary_layout.addWidget(self.lbl_topic)
        self.lbl_summary = QLabel("")
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setStyleSheet("font-size: 12px; color: #555; background: transparent;")
        summary_layout.addWidget(self.lbl_summary)
        right_layout.addWidget(self.summary_frame)

        # 实体统计标签栏
        self.stats_bar = QHBoxLayout()
        self.stats_bar_widget = QWidget()
        self.stats_bar_layout = QHBoxLayout(self.stats_bar_widget)
        self.stats_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.stats_bar_layout.setSpacing(6)
        self.stats_bar_widget.setVisible(False)
        right_layout.addWidget(self.stats_bar_widget)

        # 实体表格
        table_header = QLabel("提取的实体:")
        table_header.setStyleSheet("font-weight: bold; background: transparent;")
        right_layout.addWidget(table_header)
        self.entity_table = QTableWidget()
        self.entity_table.setColumnCount(4)
        self.entity_table.setHorizontalHeaderLabels(["类型", "值", "上下文", "置信度"])
        self.entity_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.entity_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.entity_table.setAlternatingRowColors(True)
        self.entity_table.verticalHeader().setVisible(False)
        self.entity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.entity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        right_layout.addWidget(self.entity_table, 1)

        splitter.addWidget(right)
        splitter.setSizes([420, 580])
        layout.addWidget(splitter, 1)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文档", "",
            "文档文件 (*.docx *.md *.xlsx *.txt *.pdf *.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return

        try:
            uploaded = self.document_workflow.upload_document(Path(path).name, Path(path).read_bytes())
            result = self.document_workflow.parse_document(uploaded["id"], include_text=True)
        except Exception as e:
            QMessageBox.critical(self, "解析失败", str(e))
            return

        doc = DocumentDAO.get_by_id(uploaded["id"])
        text = result["text"]

        self.current_doc = doc
        self.lbl_file.setText(f"{doc.filename}")
        char_count = len(text)
        line_count = text.count("\n") + 1
        self.lbl_doc_info.setText(f"ID:{doc.id}  |  {doc.file_type.upper()}  |  {char_count} 字  |  {line_count} 行")
        self.txt_content.setPlainText(text)
        self.btn_extract.setEnabled(True)
        self.btn_reextract.setEnabled(True)
        self.entity_table.setRowCount(0)
        self.current_entities = []
        self._set_export_enabled(False)
        self.summary_frame.setVisible(False)
        self.stats_bar_widget.setVisible(False)

    def _open_batch_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "批量选择文档", "",
            "文档文件 (*.docx *.md *.xlsx *.txt *.pdf *.png *.jpg *.jpeg *.bmp)"
        )
        if not paths:
            return

        self.btn_open.setEnabled(False)
        self.btn_batch.setEnabled(False)
        self.btn_extract.setEnabled(False)
        self.btn_reextract.setEnabled(False)
        self.btn_batch.setText("批量提取中...")
        self.lbl_file.setText(f"批量处理 {len(paths)} 个文件")
        self.lbl_doc_info.setText("")
        self.txt_content.setPlainText("\n".join(Path(p).name for p in paths))
        self.progress.setVisible(True)
        self.progress.setRange(0, len(paths))
        self.progress.setValue(0)
        self.entity_table.setRowCount(0)
        self.current_entities = []
        self.current_doc = None
        self._set_export_enabled(False)
        self.summary_frame.setVisible(False)
        self.stats_bar_widget.setVisible(False)

        self.batch_worker = ProgressTaskWorker(
            lambda progress: self._run_batch_extract_task(paths, progress),
            error_prefix="batch entity extraction",
        )
        self.batch_worker.progress.connect(self._on_batch_progress_event)
        self.batch_worker.succeeded.connect(self._on_batch_done)
        self.batch_worker.failed.connect(self._on_batch_error)
        self.batch_worker.start()

    @staticmethod
    def _run_batch_extract_task(paths: list[str], progress) -> dict:
        loop = asyncio.new_event_loop()
        try:
            extractor = EntityExtractor()
            all_entities = []
            docs_count = 0
            failures = []
            total = len(paths)
            document_workflow = DocumentWorkflow()

            for i, path in enumerate(paths, start=1):
                src_path = Path(path)
                progress({"current": i, "total": total, "filename": src_path.name})
                try:
                    uploaded = document_workflow.upload_document(src_path.name, src_path.read_bytes())
                    document_workflow.parse_document(uploaded["id"])
                    doc = DocumentDAO.get_by_id(uploaded["id"])
                    text = doc.raw_text or ""

                    result = loop.run_until_complete(extractor.extract(text))
                    entities = result.get("entities", [])
                    if entities:
                        EntityDAO.create_batch(doc.id, entities)
                        for entity in entities:
                            entity = dict(entity)
                            entity["document"] = src_path.name
                            all_entities.append(entity)
                    docs_count += 1
                except Exception as e:
                    failures.append({"filename": src_path.name, "error": str(e)})

            return {
                "documents": docs_count,
                "entities": all_entities,
                "failures": failures,
            }
        finally:
            loop.close()

    def _start_extract(self):
        if not self.current_doc or not self.current_doc.raw_text:
            text = self.txt_content.toPlainText()
            if not text:
                QMessageBox.warning(self, "提示", "没有可提取的文本内容")
                return
        else:
            text = self.current_doc.raw_text
            existing_entities = EntityDAO.get_by_document(self.current_doc.id)
            if existing_entities:
                entities = [
                    {
                        "type": e.entity_type,
                        "value": e.entity_value,
                        "context": e.context or "",
                        "confidence": e.confidence or 0.0,
                    }
                    for e in existing_entities
                ]
                self.current_entities = entities
                self._set_export_enabled(bool(entities))
                self.summary_frame.setVisible(False)
                self._render_entities(entities)
                QMessageBox.information(self, "提示", "当前文档已有提取结果，已直接加载。若需重新生成，请使用“清除并重新提取”。")
                return

        self.btn_extract.setEnabled(False)
        self.btn_reextract.setEnabled(False)
        self.btn_extract.setText("提取中...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

        self.worker = TaskWorker(
            lambda: self._run_extract_task(text),
            error_prefix="entity extraction",
        )
        self.worker.succeeded.connect(self._on_extract_done)
        self.worker.failed.connect(self._on_extract_error)
        self.worker.start()

    @staticmethod
    def _run_extract_task(text: str) -> dict:
        loop = asyncio.new_event_loop()
        try:
            extractor = EntityExtractor()
            return loop.run_until_complete(extractor.extract(text))
        finally:
            loop.close()

    def _clear_and_reextract(self):
        if not self.current_doc:
            QMessageBox.warning(self, "提示", "请先选择一个文档")
            return

        confirm = QMessageBox.question(
            self,
            "确认重新提取",
            "将删除当前文档已有实体并重新提取，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        EntityDAO.delete_by_document(self.current_doc.id)
        self.current_entities = []
        self.entity_table.setRowCount(0)
        self.stats_bar_widget.setVisible(False)
        self._set_export_enabled(False)
        self._start_extract()

    def _render_entities(self, entities: list[dict]):
        self._update_stats_bar(entities)
        self.entity_table.setRowCount(len(entities))
        for i, e in enumerate(entities):
            etype = e.get("type", "")
            self.entity_table.setCellWidget(i, 0, _type_badge(etype))
            self.entity_table.setItem(i, 1, QTableWidgetItem(e.get("value", "")))
            self.entity_table.setItem(i, 2, QTableWidgetItem(e.get("context", "")))

            conf = e.get("confidence", 0)
            conf_item = QTableWidgetItem(f"{conf:.0%}" if conf else "")
            conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if conf and conf >= 0.9:
                conf_item.setForeground(QColor("#52C41A"))
            elif conf and conf >= 0.75:
                conf_item.setForeground(QColor("#FAAD14"))
            elif conf:
                conf_item.setForeground(QColor("#FF4D4F"))
            self.entity_table.setItem(i, 3, conf_item)
        self.entity_table.resizeRowsToContents()

    def _on_extract_done(self, result: dict):
        self.progress.setVisible(False)
        self.btn_extract.setEnabled(True)
        self.btn_reextract.setEnabled(bool(self.current_doc))
        self.btn_extract.setText("提取实体信息")

        if result.get("parse_error"):
            QMessageBox.warning(self, "提取失败", "LLM返回结果解析失败，请重试")
            return

        entities = result.get("entities", [])
        self.current_entities = entities
        self._set_export_enabled(bool(entities))
        summary = result.get("summary", "")
        topic = result.get("topic", "")

        # 存入数据库
        if self.current_doc and entities:
            EntityDAO.create_batch(self.current_doc.id, entities)

        # 显示摘要卡片
        if topic or summary:
            self.summary_frame.setVisible(True)
            self.lbl_topic.setText(f"📌 {topic}" if topic else "")
            self.lbl_summary.setText(summary)
        else:
            self.summary_frame.setVisible(False)

        self._render_entities(entities)
        QMessageBox.information(self, "提取完成", f"共提取 {len(entities)} 个实体")

    def _on_batch_progress_event(self, event: dict):
        current = event.get("current", 0)
        total = event.get("total", 0)
        filename = event.get("filename", "")
        self.progress.setValue(current)
        self.lbl_doc_info.setText(f"批量提取进度: {current}/{total}  |  {filename}")

    def _on_batch_done(self, result: dict):
        self.progress.setVisible(False)
        self.btn_open.setEnabled(True)
        self.btn_batch.setEnabled(True)
        self.btn_batch.setText("批量提取")
        self.btn_extract.setEnabled(False)
        self.btn_reextract.setEnabled(False)

        entities = result.get("entities", [])
        failures = result.get("failures", [])
        docs_count = result.get("documents", 0)
        self.current_entities = entities
        self._set_export_enabled(bool(entities))
        self.lbl_file.setText(f"批量提取完成: {docs_count}/{docs_count + len(failures)} 个文件")
        self.lbl_doc_info.setText(f"共提取 {len(entities)} 个实体，失败 {len(failures)} 个文件")
        if failures:
            detail = "\n".join(f"{f['filename']}: {f['error']}" for f in failures[:8])
            self.txt_content.setPlainText(f"批量提取完成，但有 {len(failures)} 个文件失败:\n{detail}")
        else:
            self.txt_content.setPlainText("批量提取完成，所有文件处理成功。")
        self._render_entities(entities)
        QMessageBox.information(
            self,
            "批量提取完成",
            f"处理成功 {docs_count} 个文件，提取 {len(entities)} 个实体，失败 {len(failures)} 个文件"
        )

    def _on_batch_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_open.setEnabled(True)
        self.btn_batch.setEnabled(True)
        self.btn_batch.setText("批量提取")
        self.btn_extract.setEnabled(False)
        self.btn_reextract.setEnabled(False)
        QMessageBox.critical(self, "批量提取失败", msg)

    def _set_export_enabled(self, enabled: bool):
        self.btn_export_csv.setEnabled(enabled)
        self.btn_export_xlsx.setEnabled(enabled)

    def _export_entities(self, file_format: str):
        if not self.current_entities:
            QMessageBox.warning(self, "提示", "没有可导出的实体数据")
            return

        if file_format == "csv":
            path, _ = QFileDialog.getSaveFileName(self, "导出CSV", "entities.csv", "CSV文件 (*.csv)")
            if not path:
                return
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["type", "value", "context", "confidence"],
                    extrasaction="ignore",
                )
                writer.writeheader()
                writer.writerows(self.current_entities)
        else:
            path, _ = QFileDialog.getSaveFileName(self, "导出Excel", "entities.xlsx", "Excel文件 (*.xlsx)")
            if not path:
                return
            from openpyxl import Workbook

            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Entities"
            headers = ["type", "value", "context", "confidence"]
            sheet.append(headers)
            for entity in self.current_entities:
                sheet.append([entity.get(h, "") for h in headers])
            workbook.save(path)

        QMessageBox.information(self, "导出完成", f"实体数据已导出到:\n{path}")

    def _update_stats_bar(self, entities: list):
        """更新实体类型统计标签栏"""
        # 清空旧标签
        while self.stats_bar_layout.count():
            item = self.stats_bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not entities:
            self.stats_bar_widget.setVisible(False)
            return

        type_counts = {}
        for e in entities:
            t = e.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        total_lbl = QLabel(f"共 {len(entities)} 个实体:")
        total_lbl.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
        self.stats_bar_layout.addWidget(total_lbl)

        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            fg, bg, cn = ENTITY_COLORS.get(t, ("#8C8C8C", "#F5F5F5", t))
            chip = QLabel(f"{cn} {c}")
            chip.setStyleSheet(f"""
                background: {bg}; color: {fg}; font-size: 11px; font-weight: bold;
                border-radius: 10px; padding: 3px 10px;
            """)
            self.stats_bar_layout.addWidget(chip)

        self.stats_bar_layout.addStretch()
        self.stats_bar_widget.setVisible(True)

    def _on_extract_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_extract.setEnabled(True)
        self.btn_reextract.setEnabled(bool(self.current_doc))
        self.btn_extract.setText("提取实体信息")
        QMessageBox.critical(self, "提取失败", msg)
