from __future__ import annotations

import asyncio

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from bibtex_mvp.application.resolver import SingleEntryResolver
from bibtex_mvp.domain.bibtex_builder import build_bibtex_for_candidate
from bibtex_mvp.domain.models import BibKeyRule, CandidateRecord, ResolutionResult, ResultStatus
from bibtex_mvp.infra.scholar_url import build_scholar_search_url

from .debug_panel import DebugPanel
from .widgets import CandidateTable


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("参考文献转 BibTeX MVP")
        self.resize(1200, 850)
        self.resolver = SingleEntryResolver()
        self.current_result: ResolutionResult | None = None
        self.bulk_confirmed_candidates: list[tuple[CandidateRecord, str | None]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout()
        root.setLayout(root_layout)

        root_layout.addWidget(QLabel("输入 DOI、文献标题或完整参考文献字符串"))
        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("仅支持单条输入")
        self.input_edit.setFixedHeight(120)
        root_layout.addWidget(self.input_edit)

        action_layout = QHBoxLayout()
        root_layout.addLayout(action_layout)

        self.resolve_btn = QPushButton("开始检索并生成")
        self.resolve_btn.clicked.connect(self.on_resolve_clicked)
        action_layout.addWidget(self.resolve_btn)

        self.confirm_btn = QPushButton("确认当前候选")
        self.confirm_btn.clicked.connect(self.on_confirm_candidate_clicked)
        self.confirm_btn.setVisible(False)
        action_layout.addWidget(self.confirm_btn)

        self.confirm_all_btn = QPushButton("确认全部候选")
        self.confirm_all_btn.clicked.connect(self.on_confirm_all_candidates_clicked)
        self.confirm_all_btn.setVisible(False)
        action_layout.addWidget(self.confirm_all_btn)

        self.candidate_scholar_btn = QPushButton("在 Scholar 打开当前候选")
        self.candidate_scholar_btn.clicked.connect(self.on_open_candidate_scholar_clicked)
        self.candidate_scholar_btn.setVisible(False)
        self.candidate_scholar_btn.setEnabled(False)
        action_layout.addWidget(self.candidate_scholar_btn)

        self.scholar_btn = QPushButton("在 Scholar 打开当前输入")
        self.scholar_btn.clicked.connect(self.on_scholar_clicked)
        self.scholar_btn.setVisible(False)
        action_layout.addWidget(self.scholar_btn)

        self.copy_btn = QPushButton("复制 BibTeX")
        self.copy_btn.clicked.connect(self.on_copy_clicked)
        self.copy_btn.setEnabled(False)
        action_layout.addWidget(self.copy_btn)

        self.key_rule_combo = QComboBox()
        self.key_rule_combo.addItem("作者姓 + 年份（例：Zhou2007）", BibKeyRule.AUTHOR_YEAR)
        self.key_rule_combo.addItem("作者姓 + 年份 + 标题首词（例：Zhou2007Functional）", BibKeyRule.AUTHOR_YEAR_TITLE)
        self.key_rule_combo.addItem("标题首词 + 年份（例：Functional2007）", BibKeyRule.TITLE_YEAR)
        self.key_rule_combo.currentIndexChanged.connect(self.on_key_rule_changed)
        action_layout.addWidget(self.key_rule_combo)
        action_layout.addStretch(1)

        fields_group = QGroupBox("结果信息")
        fields_layout = QFormLayout()
        fields_group.setLayout(fields_layout)
        root_layout.addWidget(fields_group)

        self.raw_input_line = QLineEdit()
        self.raw_input_line.setReadOnly(True)
        fields_layout.addRow("原始输入", self.raw_input_line)

        self.title_line = QLineEdit()
        self.title_line.setReadOnly(True)
        fields_layout.addRow("标题", self.title_line)

        self.authors_line = QLineEdit()
        self.authors_line.setReadOnly(True)
        fields_layout.addRow("作者", self.authors_line)

        self.year_line = QLineEdit()
        self.year_line.setReadOnly(True)
        fields_layout.addRow("年份", self.year_line)

        self.doi_line = QLineEdit()
        self.doi_line.setReadOnly(True)
        fields_layout.addRow("DOI", self.doi_line)

        self.status_line = QLineEdit()
        self.status_line.setReadOnly(True)
        fields_layout.addRow("状态", self.status_line)

        root_layout.addWidget(QLabel("BibTeX"))
        self.bibtex_edit = QPlainTextEdit()
        self.bibtex_edit.setReadOnly(True)
        self.bibtex_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.bibtex_edit.setFixedHeight(210)
        root_layout.addWidget(self.bibtex_edit)

        root_layout.addWidget(QLabel("候选列表"))
        self.candidate_table = CandidateTable()
        self.candidate_table.setMinimumHeight(200)
        self.candidate_table.itemSelectionChanged.connect(self.on_candidate_selection_changed)
        self.candidate_table.cellDoubleClicked.connect(self.on_candidate_row_double_clicked)
        root_layout.addWidget(self.candidate_table)

        self.debug_panel = DebugPanel()
        root_layout.addWidget(self.debug_panel)
        root_layout.setAlignment(self.debug_panel, Qt.AlignmentFlag.AlignLeft)

    def current_key_rule(self) -> BibKeyRule:
        return self.key_rule_combo.currentData()

    def on_resolve_clicked(self) -> None:
        raw = self.input_edit.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "输入为空", "请先输入 DOI、标题或完整参考文献字符串")
            return

        self.resolve_btn.setEnabled(False)
        try:
            result = asyncio.run(
                self.resolver.resolve(
                    raw_input=raw,
                    key_rule=self.current_key_rule(),
                    config=self.debug_panel.to_config(),
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "检索失败", f"{exc}")
            self.resolve_btn.setEnabled(True)
            return
        self.resolve_btn.setEnabled(True)
        self.current_result = result
        self.bulk_confirmed_candidates = []
        self.render_result(result)

    def on_confirm_candidate_clicked(self) -> None:
        if not self.current_result:
            return
        candidate = self.candidate_table.selected_candidate()
        if not candidate:
            QMessageBox.information(self, "未选中候选", "请先在候选列表中选中一条记录")
            return
        self.confirm_btn.setEnabled(False)
        try:
            resolved = asyncio.run(
                self.resolver.finalize_candidate(
                    pending_result=self.current_result,
                    candidate=candidate,
                    key_rule=self.current_key_rule(),
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "确认失败", f"{exc}")
            self.confirm_btn.setEnabled(True)
            return
        self.confirm_btn.setEnabled(True)
        self.current_result = resolved
        self.bulk_confirmed_candidates = []
        self.render_result(resolved)

    def on_confirm_all_candidates_clicked(self) -> None:
        if not self.current_result:
            return
        if self.current_result.status != ResultStatus.PENDING:
            return
        if not self.current_result.candidates:
            QMessageBox.information(self, "没有候选", "当前没有可确认的候选结果")
            return

        self.confirm_all_btn.setEnabled(False)
        try:

            async def _finalize_all() -> list[ResolutionResult]:
                tasks = [
                    self.resolver.finalize_candidate(
                        pending_result=self.current_result,
                        candidate=candidate,
                        key_rule=self.current_key_rule(),
                    )
                    for candidate in self.current_result.candidates
                ]
                return await asyncio.gather(*tasks)

            finalized_results = asyncio.run(_finalize_all())
        except Exception as exc:
            QMessageBox.critical(self, "批量确认失败", f"{exc}")
            self.confirm_all_btn.setEnabled(True)
            return

        self.confirm_all_btn.setEnabled(True)
        confirmed: list[tuple[CandidateRecord, str | None]] = []
        for result in finalized_results:
            if result.selected is None:
                continue
            confirmed.append((result.selected, result.bibtex_base))

        if not confirmed:
            QMessageBox.warning(self, "生成失败", "全部候选都未能生成 BibTeX")
            return

        self.bulk_confirmed_candidates = confirmed
        combined_bibtex = self._build_bulk_bibtex(self.current_key_rule())

        self.current_result.status = ResultStatus.SUCCESS
        self.current_result.bibtex = combined_bibtex
        self.current_result.selected = None
        self.current_result.doi = None
        self.current_result.message = f"已确认全部候选，共 {len(confirmed)} 条"
        self.render_result(self.current_result)

    def on_open_candidate_scholar_clicked(self) -> None:
        candidate = self.candidate_table.selected_candidate()
        if not candidate:
            QMessageBox.information(self, "未选中候选", "请先在候选列表中选中一条记录")
            return
        self._open_candidate_scholar(candidate)

    def on_candidate_row_double_clicked(self, row: int, column: int) -> None:
        _ = (row, column)
        candidate = self.candidate_table.selected_candidate()
        if candidate:
            self._open_candidate_scholar(candidate)

    def on_candidate_selection_changed(self) -> None:
        candidate = self.candidate_table.selected_candidate()
        can_open = (
            self.current_result is not None
            and self.current_result.status == ResultStatus.PENDING
            and candidate is not None
        )
        self.candidate_scholar_btn.setEnabled(can_open)

    def on_scholar_clicked(self) -> None:
        if self.current_result and self.current_result.scholar_url:
            QDesktopServices.openUrl(QUrl(self.current_result.scholar_url))

    def on_copy_clicked(self) -> None:
        text = self.bibtex_edit.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "复制成功", "BibTeX 已复制到剪贴板")

    def on_key_rule_changed(self) -> None:
        if not self.current_result:
            return
        if self.current_result.status != ResultStatus.SUCCESS:
            return
        if self.bulk_confirmed_candidates:
            self.current_result.bibtex = self._build_bulk_bibtex(self.current_key_rule())
            self.bibtex_edit.setPlainText(self.current_result.bibtex or "")
            return
        self.current_result = self.resolver.rebuild_result_bibtex(self.current_result, self.current_key_rule())
        self.bibtex_edit.setPlainText(self.current_result.bibtex or "")

    def render_result(self, result: ResolutionResult) -> None:
        self.raw_input_line.setText(result.raw_input)

        selected = result.selected
        title = selected.title if selected else (result.parsed_title or "")
        authors = selected.authors if selected else result.parsed_authors
        year = selected.year if selected and selected.year is not None else result.parsed_year
        doi = selected.doi if selected else (result.doi or "")

        self.title_line.setText(title or "")
        self.authors_line.setText(", ".join(authors) if authors else "")
        self.year_line.setText(str(year) if year else "")
        self.doi_line.setText(doi or "")
        self.status_line.setText(result.status.value)
        self.bibtex_edit.setPlainText(result.bibtex or "")

        self.candidate_table.load_candidates(result.candidates)
        show_candidate_controls = result.status == ResultStatus.PENDING and len(result.candidates) > 0
        self.confirm_btn.setVisible(show_candidate_controls)
        self.confirm_all_btn.setVisible(show_candidate_controls)
        self.candidate_scholar_btn.setVisible(show_candidate_controls)
        self.on_candidate_selection_changed()

        show_scholar = result.status in {ResultStatus.PENDING, ResultStatus.FAILED}
        self.scholar_btn.setVisible(show_scholar and bool(result.scholar_url))
        self.copy_btn.setEnabled(result.status == ResultStatus.SUCCESS and bool(result.bibtex))

    def _open_candidate_scholar(self, candidate: CandidateRecord) -> None:
        query_parts: list[str] = [candidate.title]
        if candidate.authors:
            first_author = candidate.authors[0].split(",", 1)[0].strip()
            if first_author:
                query_parts.append(first_author)
        if candidate.year:
            query_parts.append(str(candidate.year))
        url = build_scholar_search_url(" ".join(query_parts))
        QDesktopServices.openUrl(QUrl(url))

    def _build_bulk_bibtex(self, key_rule: BibKeyRule) -> str:
        blocks: list[str] = []
        for candidate, base_bibtex in self.bulk_confirmed_candidates:
            bibtex, _ = build_bibtex_for_candidate(candidate, key_rule, base_bibtex)
            if bibtex.strip():
                blocks.append(bibtex.strip())
        return "\n\n".join(blocks)

