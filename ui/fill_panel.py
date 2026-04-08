"""表格自动填写面板"""
import asyncio
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QFileDialog, QTableWidget, QTableWidgetItem, QSplitter,
    QProgressBar, QMessageBox, QListWidget, QHeaderView, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from core.template_filler import TemplateFiller
from core.semantic_matcher import SemanticMatcher
from db.database import EntityDAO, TemplateDAO
from ui.fill_confirm_dialog import FillConfirmDialog
from config import UPLOAD_DIR, OUTPUT_DIR
from utils.file_utils import safe_copy
import json
import os
import shutil as sh
from datetime import datetime


class MatchWorker(QThread):
    """语义匹配线程"""
    finished = pyqtSignal(dict, dict)  # match_result, analysis
    error = pyqtSignal(str)

    def __init__(self, template_path, entities):
        super().__init__()
        self.template_path = template_path
        self.entities = entities

    def run(self):
        loop = asyncio.new_event_loop()
        try:
            filler = TemplateFiller()
            analysis = loop.run_until_complete(filler.analyze_template(self.template_path))
            field_names = analysis.get("field_names", [])
            if not field_names:
                self.error.emit("模板中未找到需要填写的字段")
                return
            matcher = SemanticMatcher()
            match_result = loop.run_until_complete(matcher.match(field_names, self.entities))
            self.finished.emit(match_result, analysis)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            loop.close()


class FillPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.current_template_path = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 模板选择
        tpl_bar = QHBoxLayout()
        self.btn_open_tpl = QPushButton("选择模板表格")
        self.btn_open_tpl.clicked.connect(self._open_template)
        self.lbl_tpl = QLabel("未选择模板")
        tpl_bar.addWidget(self.btn_open_tpl)
        tpl_bar.addWidget(self.lbl_tpl, 1)
        layout.addLayout(tpl_bar)

        # 中间区域
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：识别的字段 + 数据库实体
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        fields_group = QGroupBox("模板字段")
        fields_layout = QVBoxLayout(fields_group)
        self.fields_list = QListWidget()
        fields_layout.addWidget(self.fields_list)
        left_layout.addWidget(fields_group)

        entities_group = QGroupBox("数据库中的实体")
        entities_layout = QVBoxLayout(entities_group)
        self.btn_refresh = QPushButton("刷新实体列表")
        self.btn_refresh.clicked.connect(self._refresh_entities)
        entities_layout.addWidget(self.btn_refresh)
        self.entity_table = QTableWidget()
        self.entity_table.setColumnCount(3)
        self.entity_table.setHorizontalHeaderLabels(["类型", "值", "置信度"])
        self.entity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.entity_table.verticalHeader().setVisible(False)
        self.entity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.entity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.entity_table.setAlternatingRowColors(True)
        entities_layout.addWidget(self.entity_table)
        left_layout.addWidget(entities_group)

        splitter.addWidget(left)

        # 右侧：填写结果
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_fill = QPushButton("开始自动填写")
        self.btn_fill.clicked.connect(self._start_fill)
        self.btn_fill.setEnabled(False)
        right_layout.addWidget(self.btn_fill)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        right_layout.addWidget(self.progress)

        # 填写结果卡片
        self.result_frame = QFrame()
        self.result_frame.setStyleSheet("""
            QFrame {
                background: #F0F5FF;
                border: 1px solid #D6E4FF;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        self.result_frame.setVisible(False)
        result_card_layout = QVBoxLayout(self.result_frame)
        result_card_layout.setContentsMargins(12, 8, 12, 8)
        result_card_layout.setSpacing(4)
        self.lbl_result_title = QLabel("")
        self.lbl_result_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #5B8DEF; background: transparent;")
        result_card_layout.addWidget(self.lbl_result_title)
        self.lbl_result_detail = QLabel("")
        self.lbl_result_detail.setWordWrap(True)
        self.lbl_result_detail.setStyleSheet("font-size: 12px; color: #555; background: transparent;")
        result_card_layout.addWidget(self.lbl_result_detail)
        self.lbl_result_path = QLabel("")
        self.lbl_result_path.setWordWrap(True)
        self.lbl_result_path.setStyleSheet("font-size: 11px; color: #888; background: transparent;")
        result_card_layout.addWidget(self.lbl_result_path)
        right_layout.addWidget(self.result_frame)

        # 空状态提示
        self.lbl_empty_hint = QLabel("选择模板并点击「开始自动填写」后，结果将显示在这里")
        self.lbl_empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty_hint.setStyleSheet("color: #BBB; font-size: 12px; padding: 40px;")
        right_layout.addWidget(self.lbl_empty_hint, 1)

        self.btn_open_result = QPushButton("打开结果文件")
        self.btn_open_result.clicked.connect(self._open_result)
        self.btn_open_result.setEnabled(False)
        right_layout.addWidget(self.btn_open_result)

        splitter.addWidget(right)
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, 1)

    def _open_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模板表格", "",
                                               "表格文件 (*.xlsx *.docx)")
        if not path:
            return

        dest = safe_copy(path, UPLOAD_DIR)
        self.current_template_path = str(dest)
        self.lbl_tpl.setText(Path(path).name)

        # 分析模板字段
        try:
            loop = asyncio.new_event_loop()
            try:
                filler = TemplateFiller()
                analysis = loop.run_until_complete(filler.analyze_template(str(dest)))
            finally:
                loop.close()

            self.fields_list.clear()
            for f in analysis.get("field_names", []):
                self.fields_list.addItem(f)

            TemplateDAO.create(Path(path).name, str(dest), json.dumps(analysis, ensure_ascii=False))
            self.btn_fill.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "模板分析失败", str(e))

    def _refresh_entities(self):
        entities = EntityDAO.get_all()
        self.entity_table.setRowCount(len(entities))
        for i, e in enumerate(entities):
            self.entity_table.setItem(i, 0, QTableWidgetItem(e.entity_type))
            self.entity_table.setItem(i, 1, QTableWidgetItem(e.entity_value))
            self.entity_table.setItem(i, 2, QTableWidgetItem(str(e.confidence or "")))

    def _start_fill(self):
        if not self.current_template_path:
            QMessageBox.warning(self, "提示", "请先选择模板表格")
            return

        entities = EntityDAO.get_all()
        if not entities:
            QMessageBox.warning(self, "提示", "数据库中没有提取的实体，请先在'信息提取'面板提取文档信息")
            return

        self.entity_list = [{"type": e.entity_type, "value": e.entity_value,
                             "confidence": e.confidence} for e in entities]

        self.btn_fill.setEnabled(False)
        self.btn_fill.setText("匹配中...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

        self.match_worker = MatchWorker(self.current_template_path, self.entity_list)
        self.match_worker.finished.connect(self._on_match_done)
        self.match_worker.error.connect(self._on_fill_error)
        self.match_worker.start()

    def _on_match_done(self, match_result, analysis):
        self.progress.setVisible(False)
        self.btn_fill.setEnabled(True)
        self.btn_fill.setText("开始自动填写")

        matches = match_result.get("matches", [])
        unmatched = match_result.get("unmatched_fields", [])

        # 弹出确认对话框
        dlg = FillConfirmDialog(matches, unmatched, self.entity_list, self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            self.result_frame.setVisible(True)
            self.lbl_empty_hint.setVisible(False)
            self.lbl_result_title.setText("已取消")
            self.lbl_result_detail.setText("用户取消了填写操作")
            self.lbl_result_path.setText("")
            return

        fill_map = dlg.get_fill_map()
        if not fill_map:
            self.result_frame.setVisible(True)
            self.lbl_empty_hint.setVisible(False)
            self.lbl_result_title.setText("无需填写")
            self.lbl_result_detail.setText("没有需要填写的字段")
            self.lbl_result_path.setText("")
            return

        # 执行填写
        try:
            path = Path(self.current_template_path)
            suffix = path.suffix.lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"{path.stem}_filled_{timestamp}{suffix}"
            output_path = OUTPUT_DIR / output_name
            sh.copyfile(self.current_template_path, output_path)
            output_path.chmod(0o666)

            filler = TemplateFiller()
            fields = analysis.get("fields", [])

            if suffix == ".xlsx":
                filler._fill_xlsx(str(output_path), fields, fill_map)
            elif suffix == ".docx":
                filler._fill_docx(str(output_path), fields, fill_map)

            filled_count = sum(1 for f in fields if f["field_name"] in fill_map)
            total_count = len(fields)

            self.result_path = str(output_path)
            accuracy_str = f"{filled_count / total_count:.1%}" if total_count > 0 else "N/A"
            unmatched_names = [f["field_name"] for f in fields if f["field_name"] not in fill_map]

            self.result_frame.setVisible(True)
            self.lbl_empty_hint.setVisible(False)
            self.lbl_result_title.setText(f"填写完成 — {filled_count}/{total_count} 个字段")
            detail_parts = [f"准确率: {accuracy_str}"]
            if unmatched_names:
                detail_parts.append(f"未填写: {', '.join(unmatched_names)}")
            self.lbl_result_detail.setText("\n".join(detail_parts))
            self.lbl_result_path.setText(f"输出文件: {self.result_path}")
            self.btn_open_result.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "填写失败", str(e))

    def _on_fill_error(self, msg):
        self.progress.setVisible(False)
        self.btn_fill.setEnabled(True)
        self.btn_fill.setText("开始自动填写")
        QMessageBox.critical(self, "填写失败", msg)

    def _open_result(self):
        if hasattr(self, "result_path") and self.result_path:
            import sys
            import subprocess
            if sys.platform == "win32":
                os.startfile(self.result_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.result_path])
            else:
                subprocess.Popen(["xdg-open", self.result_path])
