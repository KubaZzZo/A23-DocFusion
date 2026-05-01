"""填写确认对话框 - 用户可预览和修改匹配结果"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class FillConfirmDialog(QDialog):
    """展示语义匹配结果，允许用户修改后确认。"""

    def __init__(self, matches: list[dict], unmatched: list[str], entities: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("填写确认 - 请检查匹配结果")
        self.setMinimumSize(700, 500)
        self.matches = matches
        self.unmatched = unmatched
        self.entities = entities
        self.confirmed_map = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        tip = QLabel("以下是系统自动匹配的结果，您可以修改匹配值后点击确认填写。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #666; font-size: 13px; background: transparent; padding: 4px;")
        layout.addWidget(tip)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["模板字段", "匹配值", "实体类型", "置信度"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)

        all_fields = self.matches + [
            {"field": field_name, "value": "", "confidence": 0, "source_entity_type": ""}
            for field_name in self.unmatched
        ]
        self.table.setRowCount(len(all_fields))
        self.field_edits = []

        for row, match in enumerate(all_fields):
            field_item = QTableWidgetItem(match.get("field", ""))
            field_item.setFlags(field_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, field_item)

            edit = QLineEdit(match.get("value", ""))
            edit.setPlaceholderText("输入或留空跳过")
            self.table.setCellWidget(row, 1, edit)
            self.field_edits.append((match.get("field", ""), edit))

            type_item = QTableWidgetItem(match.get("source_entity_type", "未匹配"))
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, type_item)

            confidence = match.get("confidence", 0)
            confidence_item = QTableWidgetItem(f"{confidence:.0%}" if confidence else "-")
            confidence_item.setFlags(confidence_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, confidence_item)

            if not match.get("value"):
                for col in range(4):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(Qt.GlobalColor.yellow)

        layout.addWidget(self.table, 1)

        stats = QLabel(f"已匹配 {len(self.matches)} 个字段 | 未匹配 {len(self.unmatched)} 个字段")
        stats.setStyleSheet("color: #888; background: transparent;")
        layout.addWidget(stats)

        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setStyleSheet("background-color: #909399;")
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)
        self.btn_confirm = QPushButton("确认填写")
        self.btn_confirm.clicked.connect(self._confirm)
        btn_bar.addWidget(self.btn_confirm)
        layout.addLayout(btn_bar)

    def _confirm(self):
        self.confirmed_map = {}
        for field_name, edit in self.field_edits:
            value = edit.text().strip()
            if value:
                self.confirmed_map[field_name] = value
        self.accept()

    def get_fill_map(self) -> dict:
        """返回用户确认后的 {字段名: 填写值} 映射。"""
        return self.confirmed_map
