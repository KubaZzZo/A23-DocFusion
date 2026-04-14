"""数据概览面板 - 展示系统统计数据"""
import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QFrame, QSplitter, QProgressBar, QScrollArea, QSizePolicy, QLineEdit,
    QFileDialog, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from datetime import datetime
from db.database import DocumentDAO, EntityDAO, TemplateDAO, CrawledArticleDAO
from llm import get_llm
from logger import get_logger

log = get_logger("ui.dashboard_panel")

# 实体类型中文名 + 颜色映射
ENTITY_TYPE_META = {
    "person":       ("人名",   "#5B8DEF"),
    "organization": ("机构",   "#52C41A"),
    "date":         ("日期",   "#FAAD14"),
    "amount":       ("金额",   "#FF4D4F"),
    "phone":        ("电话",   "#722ED1"),
    "email":        ("邮箱",   "#13C2C2"),
    "address":      ("地址",   "#EB2F96"),
    "id_number":    ("编号",   "#FA8C16"),
    "custom":       ("其他",   "#8C8C8C"),
}

DOC_TYPE_META = {
    "docx": ("DOCX", "#5B8DEF"),
    "xlsx": ("XLSX", "#52C41A"),
    "md": ("MD", "#13C2C2"),
    "txt": ("TXT", "#FAAD14"),
    "pdf": ("PDF", "#FF4D4F"),
    "png": ("PNG", "#722ED1"),
    "jpg": ("JPG", "#EB2F96"),
    "jpeg": ("JPEG", "#EB2F96"),
    "bmp": ("BMP", "#8C8C8C"),
}


ENTITY_QA_PROMPT = """你是DocFusion的实体问答助手。请只根据给定的已提取实体数据回答用户问题。
要求：
1. 如果实体数据中能找到答案，直接回答并说明依据的实体类型。
2. 如果无法确定答案，请回答“根据当前实体库无法确定”，不要编造。
3. 回答要简洁，适合桌面端展示。
"""


class EntityQAWorker(QThread):
    """基于实体库的智能问答线程"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, question: str, entities: list[dict]):
        super().__init__()
        self.question = question
        self.entities = entities

    def run(self):
        loop = asyncio.new_event_loop()
        try:
            context_lines = []
            for i, entity in enumerate(self.entities[:300], start=1):
                context_lines.append(
                    f"{i}. 类型={entity['type']}；值={entity['value']}；上下文={entity['context']}；"
                    f"置信度={entity['confidence']}"
                )
            context = "\n".join(context_lines)
            messages = [
                {"role": "system", "content": ENTITY_QA_PROMPT},
                {"role": "user", "content": f"用户问题：{self.question}\n\n已提取实体：\n{context}"},
            ]
            answer = loop.run_until_complete(get_llm().chat(messages, temperature=0.0))
            self.finished.emit(answer)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            loop.close()


class StatCard(QWidget):
    """带彩色顶部边框和图标的统计卡片"""
    def __init__(self, title: str, accent: str = "#5B8DEF", icon_char: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            StatCard {{
                background: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-top: 3px solid {accent};
                border-radius: 8px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        # 图标 + 标题行
        header = QHBoxLayout()
        if icon_char:
            icon_lbl = QLabel(icon_char)
            icon_lbl.setStyleSheet(f"font-size: 22px; color: {accent}; background: transparent;")
            header.addWidget(icon_lbl)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 13px; color: #888; background: transparent;")
        header.addWidget(title_lbl)
        header.addStretch()
        layout.addLayout(header)

        # 数值
        self.lbl_value = QLabel("0")
        self.lbl_value.setStyleSheet(f"font-size: 36px; font-weight: bold; color: {accent}; background: transparent;")
        layout.addWidget(self.lbl_value)

        # 副标题/描述
        self.lbl_sub = QLabel("")
        self.lbl_sub.setStyleSheet("font-size: 11px; color: #AAAAAA; background: transparent;")
        layout.addWidget(self.lbl_sub)

    def set_value(self, value: str, sub: str = ""):
        self.lbl_value.setText(value)
        if sub:
            self.lbl_sub.setText(sub)


class EntityTypeBar(QWidget):
    """实体类型分布条"""
    def __init__(self, type_name: str, count: int, max_count: int, color: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        # 类型标签（带色点）
        dot = QLabel("●")
        dot.setFixedWidth(14)
        dot.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")
        layout.addWidget(dot)

        name_lbl = QLabel(type_name)
        name_lbl.setFixedWidth(50)
        name_lbl.setStyleSheet("font-size: 12px; color: #333; background: transparent;")
        layout.addWidget(name_lbl)

        # 进度条
        bar = QProgressBar()
        bar.setRange(0, max(max_count, 1))
        bar.setValue(count)
        bar.setTextVisible(False)
        bar.setFixedHeight(12)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #F0F0F0;
                border: none;
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)
        layout.addWidget(bar, 1)

        # 数量
        count_lbl = QLabel(str(count))
        count_lbl.setFixedWidth(40)
        count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        count_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #555; background: transparent;")
        layout.addWidget(count_lbl)


class DashboardPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.cross_doc_entities = []
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root_layout.addWidget(self.scroll_area)

        content = QWidget()
        self.scroll_area.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 欢迎横幅
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5B8DEF, stop:1 #7EB8FF);
                border-radius: 10px;
                padding: 0;
            }
        """)
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(24, 16, 24, 16)
        banner_left = QVBoxLayout()
        welcome_title = QLabel("DocFusion 数据概览")
        welcome_title.setStyleSheet("font-size: 20px; font-weight: bold; color: white; background: transparent;")
        banner_left.addWidget(welcome_title)
        welcome_sub = QLabel("文档理解与多源数据融合系统 · 实时统计")
        welcome_sub.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.85); background: transparent;")
        banner_left.addWidget(welcome_sub)
        banner_layout.addLayout(banner_left)
        banner_layout.addStretch()
        self.btn_refresh = QPushButton("↻ 刷新")
        self.btn_refresh.setFixedSize(80, 32)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.4);
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.35); }
        """)
        self.btn_refresh.clicked.connect(self.refresh)
        banner_layout.addWidget(self.btn_refresh)
        layout.addWidget(banner)

        # 统计卡片
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)
        self.card_docs = StatCard("文档数量", "#5B8DEF", "📄")
        self.card_entities = StatCard("实体数量", "#52C41A", "🏷")
        self.card_templates = StatCard("模板数量", "#FAAD14", "📋")
        self.card_articles = StatCard("爬取文章", "#722ED1", "📰")
        for card in [self.card_docs, self.card_entities, self.card_templates, self.card_articles]:
            cards_layout.addWidget(card)
        layout.addLayout(cards_layout)

        # 下半部分：实体分布 + 最近文档 并排
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # 左：实体类型分布
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        entity_group = QGroupBox("实体类型分布")
        entity_layout = QVBoxLayout(entity_group)
        entity_layout.setContentsMargins(12, 12, 12, 12)
        entity_layout.setSpacing(6)
        self.entity_bars_container = QVBoxLayout()
        self.entity_bars_container.setSpacing(4)
        entity_layout.addLayout(self.entity_bars_container)
        entity_layout.addStretch()
        # 总计标签
        self.lbl_entity_total = QLabel("")
        self.lbl_entity_total.setStyleSheet("font-size: 11px; color: #AAA; background: transparent; padding: 4px;")
        entity_layout.addWidget(self.lbl_entity_total)
        left_layout.addWidget(entity_group)

        doc_type_group = QGroupBox("文档类型分布")
        doc_type_layout = QVBoxLayout(doc_type_group)
        doc_type_layout.setContentsMargins(12, 12, 12, 12)
        doc_type_layout.setSpacing(6)
        self.doc_type_bars_container = QVBoxLayout()
        self.doc_type_bars_container.setSpacing(4)
        doc_type_layout.addLayout(self.doc_type_bars_container)
        doc_type_layout.addStretch()
        self.lbl_doc_type_total = QLabel("")
        self.lbl_doc_type_total.setStyleSheet("font-size: 11px; color: #AAA; background: transparent; padding: 4px;")
        doc_type_layout.addWidget(self.lbl_doc_type_total)
        left_layout.addWidget(doc_type_group)

        search_group = QGroupBox("实体关键词搜索")
        search_layout = QVBoxLayout(search_group)
        search_layout.setContentsMargins(12, 12, 12, 12)
        search_layout.setSpacing(8)
        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)
        self.input_entity_search = QLineEdit()
        self.input_entity_search.setPlaceholderText("输入实体关键词，如姓名、电话、机构...")
        self.input_entity_search.returnPressed.connect(self._search_entities)
        search_bar.addWidget(self.input_entity_search, 1)
        self.btn_entity_search = QPushButton("搜索")
        self.btn_entity_search.clicked.connect(self._search_entities)
        self.btn_entity_search.setMinimumWidth(76)
        search_bar.addWidget(self.btn_entity_search)
        search_layout.addLayout(search_bar)
        self.entity_search_table = QTableWidget()
        self.entity_search_table.setColumnCount(3)
        self.entity_search_table.setHorizontalHeaderLabels(["类型", "值", "上下文"])
        self.entity_search_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.entity_search_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.entity_search_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.entity_search_table.verticalHeader().setVisible(False)
        self.entity_search_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.entity_search_table.setAlternatingRowColors(True)
        self.entity_search_table.setMinimumHeight(180)
        self.entity_search_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        search_layout.addWidget(self.entity_search_table)
        search_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(search_group)

        splitter.addWidget(left_panel)

        # 右：最近文档 + 融合分析
        right_panel = QWidget()
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(0)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setChildrenCollapsible(False)
        right_panel_layout.addWidget(right_splitter)

        right_group = QGroupBox("最近上传的文档")
        right_layout = QVBoxLayout(right_group)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)
        self.doc_table = QTableWidget()
        self.doc_table.setColumnCount(4)
        self.doc_table.setHorizontalHeaderLabels(["文件名", "类型", "状态", "上传时间"])
        self.doc_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.doc_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.doc_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.doc_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.doc_table.setAlternatingRowColors(True)
        self.doc_table.verticalHeader().setVisible(False)
        self.doc_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.doc_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.doc_table.setMinimumHeight(220)
        self.doc_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout.addWidget(self.doc_table)
        right_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        right_splitter.addWidget(right_group)

        fusion_group = QGroupBox("跨文档实体关联")
        fusion_layout = QVBoxLayout(fusion_group)
        fusion_layout.setContentsMargins(12, 12, 12, 12)
        fusion_layout.setSpacing(8)
        fusion_header = QHBoxLayout()
        fusion_header.setSpacing(8)
        fusion_hint = QLabel("展示在多个文档中重复出现的实体，体现多源数据融合结果")
        fusion_hint.setStyleSheet("font-size: 11px; color: #888; background: transparent;")
        fusion_hint.setWordWrap(True)
        fusion_header.addWidget(fusion_hint, 1)
        self.btn_export_fusion = QPushButton("导出融合报告")
        self.btn_export_fusion.clicked.connect(self._export_fusion_report)
        fusion_header.addWidget(self.btn_export_fusion)
        fusion_layout.addLayout(fusion_header)
        self.fusion_table = QTableWidget()
        self.fusion_table.setColumnCount(5)
        self.fusion_table.setHorizontalHeaderLabels(["类型", "实体", "文档数", "出现次数", "关联文档"])
        self.fusion_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.fusion_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.fusion_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.fusion_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.fusion_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.fusion_table.verticalHeader().setVisible(False)
        self.fusion_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.fusion_table.setAlternatingRowColors(True)
        self.fusion_table.setMinimumHeight(220)
        self.fusion_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        fusion_layout.addWidget(self.fusion_table)
        fusion_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        right_splitter.addWidget(fusion_group)

        qa_group = QGroupBox("实体智能问答")
        qa_layout = QVBoxLayout(qa_group)
        qa_layout.setContentsMargins(12, 12, 12, 12)
        qa_layout.setSpacing(8)
        qa_bar = QHBoxLayout()
        qa_bar.setSpacing(8)
        self.input_entity_question = QLineEdit()
        self.input_entity_question.setPlaceholderText("例如：张三的电话是多少？某公司出现在哪些文档中？")
        self.input_entity_question.returnPressed.connect(self._ask_entity_question)
        qa_bar.addWidget(self.input_entity_question, 1)
        self.btn_entity_qa = QPushButton("提问")
        self.btn_entity_qa.clicked.connect(self._ask_entity_question)
        self.btn_entity_qa.setMinimumWidth(76)
        qa_bar.addWidget(self.btn_entity_qa)
        qa_layout.addLayout(qa_bar)
        self.txt_entity_answer = QTextEdit()
        self.txt_entity_answer.setReadOnly(True)
        self.txt_entity_answer.setMinimumHeight(120)
        self.txt_entity_answer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.txt_entity_answer.setPlaceholderText("答案会基于已提取实体生成，不会编造实体库外信息。")
        qa_layout.addWidget(self.txt_entity_answer)
        qa_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        right_splitter.addWidget(qa_group)

        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 3)
        right_splitter.setStretchFactor(2, 2)
        right_splitter.setSizes([260, 280, 180])

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([500, 700])
        layout.addWidget(splitter, 1)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh(self):
        """刷新所有统计数据"""
        try:
            docs = DocumentDAO.get_all()
            entity_count = EntityDAO.count()
            type_counts = EntityDAO.count_by_type()
            self.cross_doc_entities = EntityDAO.get_cross_document_entities()
            templates = TemplateDAO.get_all()
            articles = CrawledArticleDAO.get_all()

            parsed_count = sum(1 for d in docs if d.raw_text)
            self.card_docs.set_value(str(len(docs)), f"已解析 {parsed_count} 篇")
            self.card_entities.set_value(
                str(entity_count),
                f"{len(type_counts)} 种类型" if entity_count else "暂无数据"
            )
            self.card_templates.set_value(str(len(templates)))
            self.card_articles.set_value(str(len(articles)))

            # 实体类型分布条形图
            # 清空旧的分布条
            self._clear_layout(self.entity_bars_container)

            if type_counts:
                max_count = max(type_counts.values())
                for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
                    meta = ENTITY_TYPE_META.get(t, (t, "#8C8C8C"))
                    bar = EntityTypeBar(meta[0], c, max_count, meta[1])
                    self.entity_bars_container.addWidget(bar)
                self.lbl_entity_total.setText(f"共 {entity_count} 个实体，{len(type_counts)} 种类型")
            else:
                empty_lbl = QLabel("暂无实体数据\n请先在「信息提取」面板提取文档实体")
                empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_lbl.setStyleSheet("color: #CCC; font-size: 13px; padding: 30px; background: transparent;")
                self.entity_bars_container.addWidget(empty_lbl)
                self.lbl_entity_total.setText("")

            # 文档类型分布条形图
            self._clear_layout(self.doc_type_bars_container)
            doc_type_counts = {}
            for d in docs:
                doc_type = (d.file_type or "unknown").lower()
                doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1

            if doc_type_counts:
                max_doc_count = max(doc_type_counts.values())
                for t, c in sorted(doc_type_counts.items(), key=lambda x: -x[1]):
                    meta = DOC_TYPE_META.get(t, (t.upper(), "#8C8C8C"))
                    bar = EntityTypeBar(meta[0], c, max_doc_count, meta[1])
                    self.doc_type_bars_container.addWidget(bar)
                self.lbl_doc_type_total.setText(f"共 {len(docs)} 个文档，{len(doc_type_counts)} 种格式")
            else:
                empty_doc_lbl = QLabel("暂无文档类型数据")
                empty_doc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_doc_lbl.setStyleSheet("color: #CCC; font-size: 13px; padding: 20px; background: transparent;")
                self.doc_type_bars_container.addWidget(empty_doc_lbl)
                self.lbl_doc_type_total.setText("")

            # 最近文档
            recent = docs[:20]
            self.doc_table.setRowCount(len(recent))
            for i, d in enumerate(recent):
                self.doc_table.setItem(i, 0, QTableWidgetItem(d.filename))

                type_item = QTableWidgetItem(d.file_type.upper())
                type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.doc_table.setItem(i, 1, type_item)

                status = "✔ 已解析" if d.raw_text else "○ 待解析"
                status_item = QTableWidgetItem(status)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if d.raw_text:
                    status_item.setForeground(QColor("#52C41A"))
                else:
                    status_item.setForeground(QColor("#FAAD14"))
                self.doc_table.setItem(i, 2, status_item)

                time_str = d.created_at.strftime("%m-%d %H:%M") if d.created_at else ""
                time_item = QTableWidgetItem(time_str)
                time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.doc_table.setItem(i, 3, time_item)

            if not recent:
                self.doc_table.setRowCount(1)
                empty = QTableWidgetItem("暂无文档，请上传或爬取")
                empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                empty.setForeground(QColor("#CCC"))
                self.doc_table.setItem(0, 0, empty)
                self.doc_table.setSpan(0, 0, 1, 4)

            self._render_fusion_table()
        except Exception as e:
            log.warning("刷新数据概览失败: %s", e)

    def _render_fusion_table(self):
        self.fusion_table.clearSpans()
        if not self.cross_doc_entities:
            self.fusion_table.setRowCount(1)
            empty = QTableWidgetItem("暂无跨文档重复实体，请先导入并提取多个相关文档")
            empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setForeground(QColor("#CCC"))
            self.fusion_table.setItem(0, 0, empty)
            self.fusion_table.setSpan(0, 0, 1, 5)
            self.btn_export_fusion.setEnabled(False)
            return

        self.btn_export_fusion.setEnabled(True)
        rows = self.cross_doc_entities[:30]
        self.fusion_table.setRowCount(len(rows))
        for i, item in enumerate(rows):
            meta = ENTITY_TYPE_META.get(item["type"], (item["type"], "#8C8C8C"))
            type_item = QTableWidgetItem(meta[0])
            type_item.setForeground(QColor(meta[1]))
            self.fusion_table.setItem(i, 0, type_item)
            self.fusion_table.setItem(i, 1, QTableWidgetItem(item["value"]))
            doc_count_item = QTableWidgetItem(str(item["doc_count"]))
            doc_count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fusion_table.setItem(i, 2, doc_count_item)
            count_item = QTableWidgetItem(str(item["count"]))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fusion_table.setItem(i, 3, count_item)
            self.fusion_table.setItem(i, 4, QTableWidgetItem("、".join(item["documents"])))
        self.fusion_table.resizeRowsToContents()

    def _export_fusion_report(self):
        if not self.cross_doc_entities:
            QMessageBox.warning(self, "提示", "暂无可导出的跨文档实体关联数据")
            return

        default_name = f"fusion_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "导出融合报告", default_name, "Excel文件 (*.xlsx)")
        if not path:
            return

        try:
            from openpyxl import Workbook

            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "跨文档实体关联"
            headers = ["实体类型", "实体值", "关联文档数", "出现次数", "平均置信度", "关联文档"]
            sheet.append(headers)
            for item in self.cross_doc_entities:
                avg_confidence = item.get("avg_confidence")
                sheet.append([
                    ENTITY_TYPE_META.get(item["type"], (item["type"], ""))[0],
                    item["value"],
                    item["doc_count"],
                    item["count"],
                    round(avg_confidence, 4) if avg_confidence is not None else "",
                    "；".join(item["documents"]),
                ])

            summary = workbook.create_sheet("融合统计")
            summary.append(["指标", "值"])
            summary.append(["跨文档实体数量", len(self.cross_doc_entities)])
            summary.append(["涉及文档总数", len({doc for item in self.cross_doc_entities for doc in item["documents"]})])
            summary.append(["报告生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])

            workbook.save(path)
            QMessageBox.information(self, "导出完成", f"融合报告已导出到:\n{path}")
        except Exception as e:
            log.warning("导出融合报告失败: %s", e)
            QMessageBox.critical(self, "导出失败", str(e))

    def _ask_entity_question(self):
        question = self.input_entity_question.text().strip()
        if not question:
            return

        try:
            all_entities = EntityDAO.get_all()
            if not all_entities:
                QMessageBox.warning(self, "提示", "实体库为空，请先提取文档实体")
                return

            matched = [
                e for e in all_entities
                if e.entity_value and (e.entity_value in question or question in e.entity_value)
            ]
            seed_entities = matched or all_entities
            entities = [
                {
                    "type": e.entity_type,
                    "value": e.entity_value,
                    "context": e.context or "",
                    "confidence": e.confidence if e.confidence is not None else "",
                }
                for e in seed_entities
            ]

            self.btn_entity_qa.setEnabled(False)
            self.btn_entity_qa.setText("思考中...")
            self.txt_entity_answer.setPlainText("正在基于实体库生成答案...")
            self.qa_worker = EntityQAWorker(question, entities)
            self.qa_worker.finished.connect(self._on_entity_answer)
            self.qa_worker.error.connect(self._on_entity_qa_error)
            self.qa_worker.start()
        except Exception as e:
            log.warning("实体问答启动失败: %s", e)
            QMessageBox.critical(self, "问答失败", str(e))

    def _on_entity_answer(self, answer: str):
        self.btn_entity_qa.setEnabled(True)
        self.btn_entity_qa.setText("提问")
        self.txt_entity_answer.setPlainText(answer)

    def _on_entity_qa_error(self, msg: str):
        self.btn_entity_qa.setEnabled(True)
        self.btn_entity_qa.setText("提问")
        self.txt_entity_answer.setPlainText("")
        QMessageBox.critical(self, "问答失败", msg)

    def _search_entities(self):
        keyword = self.input_entity_search.text().strip()
        if not keyword:
            self.entity_search_table.setRowCount(0)
            return

        try:
            entities = EntityDAO.search(keyword)
            self.entity_search_table.setRowCount(len(entities))
            for i, e in enumerate(entities):
                meta = ENTITY_TYPE_META.get(e.entity_type, (e.entity_type, "#8C8C8C"))
                type_item = QTableWidgetItem(meta[0])
                type_item.setForeground(QColor(meta[1]))
                self.entity_search_table.setItem(i, 0, type_item)
                self.entity_search_table.setItem(i, 1, QTableWidgetItem(e.entity_value))
                self.entity_search_table.setItem(i, 2, QTableWidgetItem(e.context or ""))
            self.entity_search_table.resizeRowsToContents()
        except Exception as e:
            log.warning("搜索实体失败: %s", e)
