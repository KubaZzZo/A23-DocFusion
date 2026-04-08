"""新闻爬虫管理面板"""
import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QCheckBox, QSpinBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QGroupBox, QSplitter, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from crawler.news_spider import NewsSpider, NEWS_SOURCES
from crawler.doc_generator import DocGenerator
from db.database import CrawledArticleDAO, DocumentDAO, EntityDAO
from core.document_parser import DocumentParser
from core.entity_extractor import EntityExtractor
from config import UPLOAD_DIR
from logger import get_logger
import shutil
from pathlib import Path

log = get_logger("ui.crawler_panel")


class CrawlWorker(QThread):
    """爬取线程"""
    progress = pyqtSignal(str, int, int, str)  # source_name, current, total, message
    article_found = pyqtSignal(dict)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, sources: list[str], count: int):
        super().__init__()
        self.sources = sources
        self.count = count

    def run(self):
        spider = None
        try:
            spider = NewsSpider()
            all_articles = []
            for src in self.sources:
                def on_progress(cur, total, message="", s=src):
                    self.progress.emit(s, cur, total, message)

                articles = spider.crawl(src, self.count, on_progress)
                for a in articles:
                    self.article_found.emit(a)
                all_articles.extend(articles)
            self.finished.emit(all_articles)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if spider:
                spider.close()


class DocGenWorker(QThread):
    """文档生成线程"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, articles: list[dict]):
        super().__init__()
        self.articles = articles

    def run(self):
        try:
            paths = DocGenerator.generate_all(self.articles)
            self.finished.emit(paths)
        except Exception as e:
            self.error.emit(str(e))


class ImportWorker(QThread):
    """导入数据库 + 实体提取线程"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, articles: list[dict]):
        super().__init__()
        self.articles = articles

    def run(self):
        try:
            total = len(self.articles)
            entity_count = 0
            for i, a in enumerate(self.articles):
                # 存入 CrawledArticle 表
                CrawledArticleDAO.create(
                    title=a.get("title", ""),
                    author=a.get("author", ""),
                    source=a.get("source", ""),
                    url=a.get("url", ""),
                    publish_date=a.get("publish_date", ""),
                    content=a.get("content", ""),
                    category=a.get("category", ""),
                )
                # 同时存入 Document 表并提取实体
                content = a.get("content", "")
                if content:
                    doc = DocumentDAO.create(
                        filename=f"crawled_{a.get('title', 'article')[:30]}.txt",
                        file_type="txt",
                        file_path="crawled"
                    )
                    DocumentDAO.update_text(doc.id, content)
                    loop = asyncio.new_event_loop()
                    try:
                        extractor = EntityExtractor()
                        result = loop.run_until_complete(extractor.extract(content))
                        entities = result.get("entities", [])
                        if entities:
                            EntityDAO.create_batch(doc.id, entities)
                            entity_count += len(entities)
                    except Exception as e:
                        log.warning("导入爬取文章时实体提取失败: %s - %s", a.get("title", ""), e)
                    finally:
                        loop.close()
                self.progress.emit(i + 1, total)
            self.finished.emit(entity_count)
        except Exception as e:
            self.error.emit(str(e))


class CrawlerPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.crawled_articles = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 上方控制区
        ctrl_layout = QHBoxLayout()

        # 新闻源选择
        src_group = QGroupBox("新闻源")
        src_layout = QVBoxLayout(src_group)
        self.source_checks = {}
        for name in NEWS_SOURCES:
            cb = QCheckBox(name)
            cb.setChecked(True)
            self.source_checks[name] = cb
            src_layout.addWidget(cb)
        ctrl_layout.addWidget(src_group)

        # 爬取设置
        settings_group = QGroupBox("设置")
        settings_layout = QVBoxLayout(settings_group)

        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("每源爬取数量:"))
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 50)
        self.spin_count.setValue(10)
        count_row.addWidget(self.spin_count)
        settings_layout.addLayout(count_row)

        self.btn_crawl = QPushButton("开始爬取")
        self.btn_crawl.clicked.connect(self._start_crawl)
        settings_layout.addWidget(self.btn_crawl)

        self.btn_gen_docs = QPushButton("生成测试文档")
        self.btn_gen_docs.clicked.connect(self._generate_docs)
        self.btn_gen_docs.setEnabled(False)
        settings_layout.addWidget(self.btn_gen_docs)

        self.btn_import = QPushButton("导入到数据库")
        self.btn_import.clicked.connect(self._import_to_db)
        self.btn_import.setEnabled(False)
        settings_layout.addWidget(self.btn_import)

        ctrl_layout.addWidget(settings_group)

        # 状态信息
        status_group = QGroupBox("状态")
        status_layout = QVBoxLayout(status_group)
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setWordWrap(True)
        status_layout.addWidget(self.lbl_status)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        status_layout.addWidget(self.progress)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(120)
        self.txt_log.setPlaceholderText("操作日志...")
        status_layout.addWidget(self.txt_log)
        ctrl_layout.addWidget(status_group, 1)

        layout.addLayout(ctrl_layout)

        # 下方：结果表格 + 文章预览
        bottom_splitter = QSplitter(Qt.Orientation.Vertical)

        # 结果表格
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(0, 0, 0, 0)

        table_bar = QHBoxLayout()
        table_bar.addWidget(QLabel("爬取结果:"))
        table_bar.addStretch()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.setObjectName("secondary")
        self.btn_select_all.setFixedWidth(60)
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_deselect_all = QPushButton("取消全选")
        self.btn_deselect_all.setObjectName("secondary")
        self.btn_deselect_all.setFixedWidth(80)
        self.btn_deselect_all.clicked.connect(self._deselect_all)
        table_bar.addWidget(self.btn_select_all)
        table_bar.addWidget(self.btn_deselect_all)
        table_layout.addLayout(table_bar)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(5)
        self.result_table.setHorizontalHeaderLabels(["标题", "来源", "作者", "日期", "内容摘要"])
        self.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.result_table.currentCellChanged.connect(self._on_row_selected)
        table_layout.addWidget(self.result_table)
        bottom_splitter.addWidget(table_widget)

        # 文章预览区
        preview_group = QGroupBox("文章预览")
        preview_layout = QVBoxLayout(preview_group)
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setPlaceholderText("点击上方表格行查看文章全文...")
        preview_layout.addWidget(self.txt_preview)
        bottom_splitter.addWidget(preview_group)
        bottom_splitter.setSizes([300, 200])

        layout.addWidget(bottom_splitter, 1)

    def _get_selected_sources(self) -> list[str]:
        return [name for name, cb in self.source_checks.items() if cb.isChecked()]

    def _log(self, text: str):
        self.txt_log.append(text)

    # ---- 爬取 ----
    def _start_crawl(self):
        sources = self._get_selected_sources()
        if not sources:
            QMessageBox.warning(self, "提示", "请至少选择一个新闻源")
            return

        self.crawled_articles.clear()
        self.result_table.setRowCount(0)
        self.btn_crawl.setEnabled(False)
        self.btn_crawl.setText("爬取中...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.lbl_status.setText(f"正在爬取: {', '.join(sources)}")
        self._log(f"开始爬取 {len(sources)} 个新闻源，每源 {self.spin_count.value()} 篇")

        self.crawl_worker = CrawlWorker(sources, self.spin_count.value())
        self.crawl_worker.progress.connect(self._on_crawl_progress)
        self.crawl_worker.article_found.connect(self._on_article_found)
        self.crawl_worker.finished.connect(self._on_crawl_done)
        self.crawl_worker.error.connect(self._on_crawl_error)
        self.crawl_worker.start()

    def _on_crawl_progress(self, source: str, current: int, total: int, message: str = ""):
        self.lbl_status.setText(f"正在爬取 [{source}]: {current}/{total}")
        if message:
            self._log(message)

    def _on_article_found(self, article: dict):
        self.crawled_articles.append(article)
        row = self.result_table.rowCount()
        self.result_table.insertRow(row)
        self.result_table.setItem(row, 0, QTableWidgetItem(article.get("title", "")))
        self.result_table.setItem(row, 1, QTableWidgetItem(article.get("source", "")))
        self.result_table.setItem(row, 2, QTableWidgetItem(article.get("author", "")))
        self.result_table.setItem(row, 3, QTableWidgetItem(article.get("publish_date", "")))
        content = article.get("content", "")
        summary = content[:100] + "..." if len(content) > 100 else content
        self.result_table.setItem(row, 4, QTableWidgetItem(summary))

    def _on_crawl_done(self, articles: list):
        self.progress.setVisible(False)
        self.btn_crawl.setEnabled(True)
        self.btn_crawl.setText("开始爬取")
        count = len(self.crawled_articles)
        self.lbl_status.setText(f"爬取完成，共获取 {count} 篇文章")
        self._log(f"爬取完成，共 {count} 篇文章")
        self.btn_gen_docs.setEnabled(count > 0)
        self.btn_import.setEnabled(count > 0)

    def _on_crawl_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_crawl.setEnabled(True)
        self.btn_crawl.setText("开始爬取")
        self.lbl_status.setText("爬取出错")
        self._log(f"错误: {msg}")
        QMessageBox.critical(self, "爬取失败", msg)

    # ---- 生成文档 ----
    def _generate_docs(self):
        if not self.crawled_articles:
            return
        self.btn_gen_docs.setEnabled(False)
        self.btn_gen_docs.setText("生成中...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self._log("开始生成测试文档...")

        self.gen_worker = DocGenWorker(self.crawled_articles)
        self.gen_worker.finished.connect(self._on_gen_done)
        self.gen_worker.error.connect(self._on_gen_error)
        self.gen_worker.start()

    def _on_gen_done(self, paths: dict):
        self.progress.setVisible(False)
        self.btn_gen_docs.setEnabled(True)
        self.btn_gen_docs.setText("生成测试文档")
        total = sum(len(v) for v in paths.values())
        self.lbl_status.setText(f"文档生成完成，共 {total} 个文件")
        self._log(f"生成完成: docx={len(paths.get('docx', []))} txt={len(paths.get('txt', []))} "
                  f"md={len(paths.get('md', []))} xlsx={len(paths.get('xlsx', []))}")
        self._log(f"输出目录: data/crawled/")
        QMessageBox.information(self, "完成", f"已生成 {total} 个测试文档到 data/crawled/ 目录")

    def _on_gen_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_gen_docs.setEnabled(True)
        self.btn_gen_docs.setText("生成测试文档")
        self._log(f"生成错误: {msg}")
        QMessageBox.critical(self, "生成失败", msg)

    # ---- 导入数据库 ----
    def _import_to_db(self):
        if not self.crawled_articles:
            return
        self.btn_import.setEnabled(False)
        self.btn_import.setText("导入中...")
        self.progress.setVisible(True)
        self.progress.setRange(0, len(self.crawled_articles))
        self._log("开始导入数据库并提取实体...")

        self.import_worker = ImportWorker(self.crawled_articles)
        self.import_worker.progress.connect(self._on_import_progress)
        self.import_worker.finished.connect(self._on_import_done)
        self.import_worker.error.connect(self._on_import_error)
        self.import_worker.start()

    def _on_import_progress(self, current: int, total: int):
        self.progress.setValue(current)
        self.lbl_status.setText(f"导入中: {current}/{total}")

    def _on_import_done(self, entity_count: int):
        self.progress.setVisible(False)
        self.btn_import.setEnabled(True)
        self.btn_import.setText("导入到数据库")
        self.lbl_status.setText(f"导入完成，提取了 {entity_count} 个实体")
        self._log(f"导入完成: {len(self.crawled_articles)} 篇文章, {entity_count} 个实体")
        QMessageBox.information(self, "完成",
                                f"已导入 {len(self.crawled_articles)} 篇文章\n提取了 {entity_count} 个实体")

    def _on_import_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_import.setEnabled(True)
        self.btn_import.setText("导入到数据库")
        self._log(f"导入错误: {msg}")
        QMessageBox.critical(self, "导入失败", msg)

    def _select_all(self):
        self.result_table.selectAll()

    def _deselect_all(self):
        self.result_table.clearSelection()

    def _on_row_selected(self, row, col, prev_row, prev_col):
        if 0 <= row < len(self.crawled_articles):
            article = self.crawled_articles[row]
            title = article.get("title", "")
            source = article.get("source", "")
            date = article.get("publish_date", "")
            content = article.get("content", "")
            self.txt_preview.setPlainText(f"【{title}】\n来源: {source}  日期: {date}\n\n{content}")
