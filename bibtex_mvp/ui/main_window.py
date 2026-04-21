from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal, Slot
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
    QProgressBar,
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


class AsyncTaskWorker(QObject):
    progress = Signal(str, int, int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        task_factory: Callable[[Callable[[str, int, int], None]], Awaitable[object]],
    ) -> None:
        super().__init__()
        self._task_factory = task_factory

    @Slot()
    def run(self) -> None:
        try:
            result = asyncio.run(self._task_factory(self._emit_progress))
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)

    def _emit_progress(self, message: str, step: int, total: int) -> None:
        self.progress.emit(message, step, total)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("参考文献转 BibTeX MVP")
        self.resize(1200, 850)
        self.resolver = SingleEntryResolver()
        self.current_result: ResolutionResult | None = None
        self.bulk_confirmed_candidates: list[tuple[CandidateRecord, str | None]] = []
        self._task_thread: QThread | None = None
        self._task_worker: AsyncTaskWorker | None = None
        self._task_error_title = "处理失败"
        self._is_busy = False
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

        progress_layout = QHBoxLayout()
        root_layout.addLayout(progress_layout)
        self.progress_label = QLabel("就绪")
        progress_layout.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar, 1)

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
        key_rule = self.current_key_rule()
        config = self.debug_panel.to_config()

        async def _task(progress_cb: Callable[[str, int, int], None]) -> object:
            result = await self.resolver.resolve(
                raw_input=raw,
                key_rule=key_rule,
                config=config,
                progress_cb=progress_cb,
            )
            progress_cb("处理完成", 1, 1)
            return result

        self._run_background_task(
            task_factory=_task,
            success_handler=self._on_resolve_success,
            start_message="正在开始检索",
            error_title="检索失败",
        )

    def on_confirm_candidate_clicked(self) -> None:
        if not self.current_result:
            return
        candidate = self.candidate_table.selected_candidate()
        if not candidate:
            QMessageBox.information(self, "未选中候选", "请先在候选列表中选中一条记录")
            return
        pending_result = self.current_result
        key_rule = self.current_key_rule()

        async def _task(progress_cb: Callable[[str, int, int], None]) -> object:
            progress_cb("正在确认候选并生成 BibTeX", 1, 3)
            resolved = await self.resolver.finalize_candidate(
                pending_result=pending_result,
                candidate=candidate,
                key_rule=key_rule,
            )
            progress_cb("正在刷新结果", 2, 3)
            progress_cb("处理完成", 3, 3)
            return resolved

        self._run_background_task(
            task_factory=_task,
            success_handler=self._on_confirm_candidate_success,
            start_message="正在确认候选",
            error_title="确认失败",
        )

    def on_confirm_all_candidates_clicked(self) -> None:
        if not self.current_result:
            return
        if self.current_result.status != ResultStatus.PENDING:
            return
        if not self.current_result.candidates:
            QMessageBox.information(self, "没有候选", "当前没有可确认的候选结果")
            return

        pending_result = self.current_result
        key_rule = self.current_key_rule()
        all_candidates = list(pending_result.candidates)

        async def _task(progress_cb: Callable[[str, int, int], None]) -> object:
            progress_cb(f"正在并行确认 {len(all_candidates)} 个候选", 1, 3)
            tasks = [
                self.resolver.finalize_candidate(
                    pending_result=pending_result,
                    candidate=candidate,
                    key_rule=key_rule,
                )
                for candidate in all_candidates
            ]
            finalized_results = await asyncio.gather(*tasks)
            progress_cb("正在汇总候选结果", 2, 3)
            progress_cb("处理完成", 3, 3)
            return finalized_results

        self._run_background_task(
            task_factory=_task,
            success_handler=self._on_confirm_all_candidates_success,
            start_message="正在确认全部候选",
            error_title="批量确认失败",
        )

    def _on_resolve_success(self, payload: object) -> None:
        if not isinstance(payload, ResolutionResult):
            return
        self.current_result = payload
        self.bulk_confirmed_candidates = []
        self.render_result(payload)

    def _on_confirm_candidate_success(self, payload: object) -> None:
        if not isinstance(payload, ResolutionResult):
            return
        self.current_result = payload
        self.bulk_confirmed_candidates = []
        self.render_result(payload)

    def _on_confirm_all_candidates_success(self, payload: object) -> None:
        if not isinstance(payload, list):
            return
        if not self.current_result:
            return
        finalized_results = [r for r in payload if isinstance(r, ResolutionResult)]
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

    def _run_background_task(
        self,
        task_factory: Callable[[Callable[[str, int, int], None]], Awaitable[object]],
        success_handler: Callable[[object], None],
        start_message: str,
        error_title: str,
    ) -> None:
        if self._task_thread is not None:
            QMessageBox.information(self, "任务进行中", "请等待当前任务完成")
            return

        self._task_error_title = error_title
        self._set_busy_ui(True)
        self._update_progress(start_message, 0, 0)

        thread = QThread(self)
        worker = AsyncTaskWorker(task_factory)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_background_task_progress)
        worker.finished.connect(success_handler)
        worker.finished.connect(self._on_background_task_finished)
        worker.failed.connect(self._on_background_task_failed)
        worker.failed.connect(self._on_background_task_finished)

        self._task_thread = thread
        self._task_worker = worker
        thread.start()

    def _on_background_task_progress(self, message: str, step: int, total: int) -> None:
        self._update_progress(message, step, total)

    def _on_background_task_failed(self, message: str) -> None:
        self._update_progress("处理失败", 0, 1)
        QMessageBox.critical(self, self._task_error_title, message)

    def _on_background_task_finished(self, _payload: object) -> None:
        self._set_busy_ui(False)
        self._cleanup_background_task()

    def _cleanup_background_task(self) -> None:
        worker = self._task_worker
        thread = self._task_thread
        self._task_worker = None
        self._task_thread = None

        if thread is not None:
            thread.quit()
            thread.wait()
            thread.deleteLater()
        if worker is not None:
            worker.deleteLater()

    def _set_busy_ui(self, is_busy: bool) -> None:
        self._is_busy = is_busy
        self.input_edit.setReadOnly(is_busy)
        self.resolve_btn.setEnabled(not is_busy)
        self.key_rule_combo.setEnabled(not is_busy)
        self.debug_panel.setEnabled(not is_busy)
        self.candidate_table.setEnabled(not is_busy)

        if is_busy:
            self.confirm_btn.setEnabled(False)
            self.confirm_all_btn.setEnabled(False)
            self.candidate_scholar_btn.setEnabled(False)
            self.scholar_btn.setEnabled(False)
            self.copy_btn.setEnabled(False)
            return

        if self.current_result:
            self.render_result(self.current_result)
        else:
            self.confirm_btn.setEnabled(False)
            self.confirm_all_btn.setEnabled(False)
            self.candidate_scholar_btn.setEnabled(False)
            self.scholar_btn.setEnabled(False)
            self.copy_btn.setEnabled(False)

    def _update_progress(self, message: str, step: int, total: int) -> None:
        self.progress_label.setText(message)
        if total <= 0:
            self.progress_bar.setRange(0, 0)
            return
        ratio = max(0.0, min(1.0, step / total))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(ratio * 100))

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
            not self._is_busy
            and self.current_result is not None
            and self.current_result.status == ResultStatus.PENDING
            and candidate is not None
        )
        self.candidate_scholar_btn.setEnabled(can_open)
        self.confirm_btn.setEnabled(can_open)

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
        self.confirm_all_btn.setEnabled(show_candidate_controls and not self._is_busy)
        self.on_candidate_selection_changed()

        show_scholar = result.status in {ResultStatus.PENDING, ResultStatus.FAILED}
        self.scholar_btn.setVisible(show_scholar and bool(result.scholar_url))
        self.scholar_btn.setEnabled(show_scholar and bool(result.scholar_url) and not self._is_busy)
        self.copy_btn.setEnabled(result.status == ResultStatus.SUCCESS and bool(result.bibtex) and not self._is_busy)

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
