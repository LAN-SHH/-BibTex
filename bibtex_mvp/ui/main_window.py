from __future__ import annotations

import asyncio
import re
from typing import Awaitable, Callable

from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
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

from bibtex_mvp.application.orchestrator import BatchCancelToken
from bibtex_mvp.application.resolver import SingleEntryResolver
from bibtex_mvp.domain.batch_splitter import split_batch_input
from bibtex_mvp.domain.bibtex_builder import build_bibtex_for_candidate
from bibtex_mvp.domain.models import (
    BatchProgressEvent,
    BatchProgressStage,
    BibKeyRule,
    CandidateRecord,
    ResolutionResult,
    ResultStatus,
    SplitReasonCode,
)
from bibtex_mvp.infra.scholar_url import build_scholar_search_url

from .batch_split_dialog import AmbiguousSplitDialog, ManualSplitDialog
from .debug_panel import DebugPanel
from .widgets import CandidateTable, ResultTable


class AsyncTaskWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        task_factory: Callable[[Callable[[object], None]], Awaitable[object]],
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

    def _emit_progress(self, payload: object) -> None:
        self.progress.emit(payload)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("参考文献转 BibTeX MVP")
        self.resize(1320, 920)
        self.resolver = SingleEntryResolver()

        self.entry_inputs: dict[int, str] = {}
        self.entry_results: dict[int, ResolutionResult | None] = {}
        self.selected_entry_index: int | None = None
        self.bulk_confirmed_candidates: dict[int, list[tuple[CandidateRecord, str | None]]] = {}

        self._task_thread: QThread | None = None
        self._task_worker: AsyncTaskWorker | None = None
        self._task_error_title = "处理失败"
        self._is_busy = False
        self._is_batch_running = False
        self._batch_cancel_token: BatchCancelToken | None = None
        self._syncing_selection = False

        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout()
        root.setLayout(root_layout)

        root_layout.addWidget(QLabel("输入 DOI、文献标题或完整参考文献字符串。支持批量粘贴。"))
        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("支持单条和批量输入")
        self.input_edit.setFixedHeight(140)
        root_layout.addWidget(self.input_edit)

        action_layout = QHBoxLayout()
        root_layout.addLayout(action_layout)

        self.resolve_btn = QPushButton("开始检索并生成")
        self.resolve_btn.clicked.connect(self.on_resolve_clicked)
        action_layout.addWidget(self.resolve_btn)

        self.cancel_btn = QPushButton("取消批量任务")
        self.cancel_btn.clicked.connect(self.on_cancel_batch_clicked)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)
        action_layout.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton("确认当前候选")
        self.confirm_btn.clicked.connect(self.on_confirm_candidate_clicked)
        self.confirm_btn.setVisible(False)
        self.confirm_btn.setEnabled(False)
        action_layout.addWidget(self.confirm_btn)

        self.confirm_all_btn = QPushButton("确认全部候选")
        self.confirm_all_btn.clicked.connect(self.on_confirm_all_candidates_clicked)
        self.confirm_all_btn.setVisible(False)
        self.confirm_all_btn.setEnabled(False)
        action_layout.addWidget(self.confirm_all_btn)

        self.candidate_scholar_btn = QPushButton("在 Scholar 打开当前候选")
        self.candidate_scholar_btn.clicked.connect(self.on_open_candidate_scholar_clicked)
        self.candidate_scholar_btn.setVisible(False)
        self.candidate_scholar_btn.setEnabled(False)
        action_layout.addWidget(self.candidate_scholar_btn)

        self.scholar_btn = QPushButton("在 Scholar 打开选中文献")
        self.scholar_btn.clicked.connect(self.on_scholar_clicked)
        self.scholar_btn.setEnabled(False)
        action_layout.addWidget(self.scholar_btn)

        self.copy_btn = QPushButton("复制当前 BibTeX")
        self.copy_btn.clicked.connect(self.on_copy_clicked)
        self.copy_btn.setEnabled(False)
        action_layout.addWidget(self.copy_btn)

        self.copy_all_btn = QPushButton("复制全部成功 BibTeX")
        self.copy_all_btn.clicked.connect(self.on_copy_all_success_clicked)
        self.copy_all_btn.setEnabled(False)
        action_layout.addWidget(self.copy_all_btn)

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

        self.summary_label = QLabel("成功 0 条 | 失败 0 条 | 待确认 0 条")
        root_layout.addWidget(self.summary_label)

        sections_layout = QHBoxLayout()
        root_layout.addLayout(sections_layout)

        success_group = QGroupBox("成功")
        success_layout = QVBoxLayout()
        success_group.setLayout(success_layout)
        self.success_table = ResultTable()
        self.success_table.setMinimumHeight(170)
        self.success_table.itemSelectionChanged.connect(lambda: self.on_result_table_selection("success"))
        success_layout.addWidget(self.success_table)
        sections_layout.addWidget(success_group, 1)

        pending_group = QGroupBox("待确认")
        pending_layout = QVBoxLayout()
        pending_group.setLayout(pending_layout)
        self.pending_table = ResultTable()
        self.pending_table.setMinimumHeight(170)
        self.pending_table.itemSelectionChanged.connect(lambda: self.on_result_table_selection("pending"))
        pending_layout.addWidget(self.pending_table)
        sections_layout.addWidget(pending_group, 1)

        failed_group = QGroupBox("失败")
        failed_layout = QVBoxLayout()
        failed_group.setLayout(failed_layout)
        self.failed_table = ResultTable()
        self.failed_table.setMinimumHeight(170)
        self.failed_table.itemSelectionChanged.connect(lambda: self.on_result_table_selection("failed"))
        failed_layout.addWidget(self.failed_table)
        sections_layout.addWidget(failed_group, 1)

        fields_group = QGroupBox("选中条目详情")
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
        self.bibtex_edit.setFixedHeight(220)
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

    def _normalize_entry(self, value: str) -> str:
        value = (value or "").replace("\u3000", " ").strip()
        value = " ".join(value.split())
        return value

    def _clear_result_detail(self) -> None:
        self.raw_input_line.clear()
        self.title_line.clear()
        self.authors_line.clear()
        self.year_line.clear()
        self.doi_line.clear()
        self.status_line.clear()
        self.bibtex_edit.clear()
        self.candidate_table.load_candidates([])

    def _initialize_entries(self, entries: list[str]) -> None:
        self.entry_inputs = {index: value for index, value in enumerate(entries, start=1)}
        self.entry_results = {index: None for index in self.entry_inputs}
        self.bulk_confirmed_candidates = {}
        self.selected_entry_index = None
        self._clear_result_detail()
        self._refresh_section_tables()

    def _get_selected_result(self) -> tuple[int, ResolutionResult] | None:
        if self.selected_entry_index is None:
            return None
        result = self.entry_results.get(self.selected_entry_index)
        if result is None:
            return None
        return self.selected_entry_index, result

    def _resolve_entries_for_run(self, raw_text: str) -> list[str] | None:
        split_result = split_batch_input(raw_text)
        if split_result.reason_code == SplitReasonCode.EMPTY_INPUT:
            QMessageBox.warning(self, "输入为空", "请先输入内容")
            return None

        items = [self._normalize_entry(item) for item in split_result.items if self._normalize_entry(item)]
        if not items:
            QMessageBox.warning(self, "输入为空", "请先输入内容")
            return None

        if split_result.is_ambiguous and len(items) >= 2:
            dialog = AmbiguousSplitDialog(items=items, ambiguous_indexes=split_result.ambiguous_indexes, parent=self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            items = [self._normalize_entry(item) for item in dialog.merged_items() if self._normalize_entry(item)]
            if not items:
                QMessageBox.warning(self, "分条为空", "分条结果为空，请重新编辑")
                return None
            return items

        if split_result.is_ambiguous and len(items) == 1:
            return self._handle_single_ambiguous_choice(items[0], split_result.reason_code)

        return items

    def _handle_single_ambiguous_choice(self, item: str, reason_code: SplitReasonCode) -> list[str] | None:
        content = "无法可靠分条，请选择下一步操作。"
        if reason_code == SplitReasonCode.TOO_SHORT:
            content = "输入过短，无法可靠分条，请选择下一步操作。"

        msg = QMessageBox(self)
        msg.setWindowTitle("分条提示")
        msg.setText(content)
        single_btn = msg.addButton("按单条处理", QMessageBox.ButtonRole.AcceptRole)
        manual_btn = msg.addButton("打开手动分条编辑", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = msg.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == single_btn:
            return [item]
        if clicked == manual_btn:
            dialog = ManualSplitDialog(raw_text=item, parent=self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            lines = [self._normalize_entry(line) for line in dialog.lines() if self._normalize_entry(line)]
            if not lines:
                return None
            if len(lines) == 1:
                return [lines[0]]
            return lines
        if clicked == cancel_btn:
            return None
        return None

    def on_resolve_clicked(self) -> None:
        raw = self.input_edit.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "输入为空", "请先输入 DOI、标题或完整参考文献字符串")
            return

        entries = self._resolve_entries_for_run(raw)
        if not entries:
            return

        if len(entries) == 1:
            self._start_single_entry(entries[0])
            return
        self._start_batch_entries(entries)

    def _start_single_entry(self, entry: str) -> None:
        self._initialize_entries([entry])
        key_rule = self.current_key_rule()
        config = self.debug_panel.to_config()

        async def _task(emit_progress: Callable[[object], None]) -> object:
            def _single_progress(message: str, step: int, total: int) -> None:
                _ = (step, total)
                emit_progress(
                    BatchProgressEvent(
                        index=1,
                        total=1,
                        stage=BatchProgressStage.ITEM_START,
                        message=message,
                    )
                )

            result = await self.resolver.resolve(
                raw_input=entry,
                key_rule=key_rule,
                config=config,
                progress_cb=_single_progress,
            )
            stage = BatchProgressStage.ITEM_FAILED if result.status == ResultStatus.FAILED else BatchProgressStage.ITEM_DONE
            emit_progress(
                BatchProgressEvent(
                    index=1,
                    total=1,
                    stage=stage,
                    message="第 1 条完成" if stage == BatchProgressStage.ITEM_DONE else "第 1 条失败",
                    result=result,
                )
            )
            emit_progress(
                BatchProgressEvent(
                    index=1,
                    total=1,
                    stage=BatchProgressStage.BATCH_DONE,
                    message="处理完成",
                )
            )
            return [result]

        self._run_background_task(
            task_factory=_task,
            success_handler=self._on_batch_task_success,
            start_message="正在开始检索",
            error_title="检索失败",
            is_batch=False,
        )

    def _start_batch_entries(self, entries: list[str]) -> None:
        self._initialize_entries(entries)
        key_rule = self.current_key_rule()
        config = self.debug_panel.to_config()
        self._batch_cancel_token = BatchCancelToken()

        async def _task(emit_progress: Callable[[object], None]) -> object:
            return await self.resolver.resolve_batch(
                raw_inputs=entries,
                key_rule=key_rule,
                config=config,
                progress_cb=lambda event: emit_progress(event),
                cancel_token=self._batch_cancel_token,
            )

        self._run_background_task(
            task_factory=_task,
            success_handler=self._on_batch_task_success,
            start_message=f"开始批量处理，共 {len(entries)} 条",
            error_title="批量检索失败",
            is_batch=True,
        )

    def on_cancel_batch_clicked(self) -> None:
        if not self._is_batch_running:
            return
        if not self._batch_cancel_token:
            return
        self._batch_cancel_token.cancel()
        self.cancel_btn.setEnabled(False)
        self.progress_label.setText("正在取消批量任务")

    def on_confirm_candidate_clicked(self) -> None:
        selected = self._get_selected_result()
        if not selected:
            QMessageBox.information(self, "未选中文献", "请先在结果区选择一条文献")
            return
        entry_index, pending_result = selected
        if pending_result.status != ResultStatus.PENDING:
            QMessageBox.information(self, "状态不支持", "当前选中文献不是待确认状态")
            return

        candidate = self.candidate_table.selected_candidate()
        if not candidate:
            QMessageBox.information(self, "未选中候选", "请先在候选列表中选中一条记录")
            return

        key_rule = self.current_key_rule()

        async def _task(emit_progress: Callable[[object], None]) -> object:
            emit_progress(
                BatchProgressEvent(
                    index=entry_index,
                    total=max(1, len(self.entry_inputs)),
                    stage=BatchProgressStage.ITEM_START,
                    message=f"正在确认第 {entry_index} 条候选",
                )
            )
            resolved = await self.resolver.finalize_candidate(
                pending_result=pending_result,
                candidate=candidate,
                key_rule=key_rule,
            )
            emit_progress(
                BatchProgressEvent(
                    index=entry_index,
                    total=max(1, len(self.entry_inputs)),
                    stage=BatchProgressStage.ITEM_DONE,
                    message=f"第 {entry_index} 条已确认",
                    result=resolved,
                )
            )
            return (entry_index, resolved)

        self._run_background_task(
            task_factory=_task,
            success_handler=self._on_confirm_candidate_success,
            start_message="正在确认候选",
            error_title="确认失败",
            is_batch=False,
        )

    def on_confirm_all_candidates_clicked(self) -> None:
        selected = self._get_selected_result()
        if not selected:
            QMessageBox.information(self, "未选中文献", "请先在结果区选择一条文献")
            return

        entry_index, pending_result = selected
        if pending_result.status != ResultStatus.PENDING:
            return
        if not pending_result.candidates:
            QMessageBox.information(self, "没有候选", "当前没有可确认的候选结果")
            return

        key_rule = self.current_key_rule()

        async def _task(emit_progress: Callable[[object], None]) -> object:
            emit_progress(
                BatchProgressEvent(
                    index=entry_index,
                    total=max(1, len(self.entry_inputs)),
                    stage=BatchProgressStage.ITEM_START,
                    message=f"正在确认第 {entry_index} 条全部候选",
                )
            )
            tasks = [
                self.resolver.finalize_candidate(
                    pending_result=pending_result,
                    candidate=candidate,
                    key_rule=key_rule,
                )
                for candidate in pending_result.candidates
            ]
            finalized_results = await asyncio.gather(*tasks)
            emit_progress(
                BatchProgressEvent(
                    index=entry_index,
                    total=max(1, len(self.entry_inputs)),
                    stage=BatchProgressStage.ITEM_DONE,
                    message=f"第 {entry_index} 条全部候选确认完成",
                )
            )
            return (entry_index, finalized_results)

        self._run_background_task(
            task_factory=_task,
            success_handler=self._on_confirm_all_candidates_success,
            start_message="正在确认全部候选",
            error_title="批量确认失败",
            is_batch=False,
        )

    def _on_confirm_candidate_success(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        entry_index, result = payload
        if not isinstance(entry_index, int) or not isinstance(result, ResolutionResult):
            return
        self.entry_results[entry_index] = result
        self.bulk_confirmed_candidates.pop(entry_index, None)
        self._refresh_section_tables()
        self._select_index(entry_index)

    def _on_confirm_all_candidates_success(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        entry_index, finalized_results = payload
        if not isinstance(entry_index, int) or not isinstance(finalized_results, list):
            return

        pending_result = self.entry_results.get(entry_index)
        if not isinstance(pending_result, ResolutionResult):
            return

        confirmed: list[tuple[CandidateRecord, str | None]] = []
        for result in finalized_results:
            if not isinstance(result, ResolutionResult):
                continue
            if result.selected is None:
                continue
            confirmed.append((result.selected, result.bibtex_base))

        if not confirmed:
            QMessageBox.warning(self, "生成失败", "全部候选都未能生成 BibTeX")
            return

        self.bulk_confirmed_candidates[entry_index] = confirmed
        pending_result.status = ResultStatus.SUCCESS
        pending_result.bibtex = self._build_bulk_bibtex(entry_index, self.current_key_rule())
        pending_result.selected = None
        pending_result.doi = None
        pending_result.message = f"已确认全部候选，共 {len(confirmed)} 条"
        self.entry_results[entry_index] = pending_result

        self._refresh_section_tables()
        self._select_index(entry_index)

    def _on_batch_task_success(self, payload: object) -> None:
        if not isinstance(payload, list):
            return
        for index, result in enumerate(payload, start=1):
            if not isinstance(result, ResolutionResult):
                continue
            if self.entry_results.get(index) is None:
                self.entry_results[index] = result
        self._refresh_section_tables()

    def _run_background_task(
        self,
        task_factory: Callable[[Callable[[object], None]], Awaitable[object]],
        success_handler: Callable[[object], None],
        start_message: str,
        error_title: str,
        is_batch: bool,
    ) -> None:
        if self._task_thread is not None:
            QMessageBox.information(self, "任务进行中", "请等待当前任务完成")
            return

        self._task_error_title = error_title
        self._set_busy_ui(True, is_batch=is_batch)
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

    def _on_background_task_progress(self, payload: object) -> None:
        if not isinstance(payload, BatchProgressEvent):
            return

        total = max(1, payload.total)
        if payload.stage == BatchProgressStage.BATCH_START:
            self._update_progress(payload.message, 0, total)
            return

        if payload.stage in {
            BatchProgressStage.ITEM_DONE,
            BatchProgressStage.ITEM_FAILED,
            BatchProgressStage.ITEM_CANCELLED,
        } and payload.result is not None:
            self.entry_results[payload.index] = payload.result
            self._refresh_section_tables()
            if self.selected_entry_index == payload.index:
                self._render_selected_result()

        completed = len([result for result in self.entry_results.values() if result is not None])
        self._update_progress(payload.message, completed, total)

        if payload.stage == BatchProgressStage.BATCH_DONE:
            self._update_progress(payload.message, total, total)

    def _on_background_task_failed(self, message: str) -> None:
        self._update_progress("处理失败", 0, 1)
        QMessageBox.critical(self, self._task_error_title, message)

    def _on_background_task_finished(self, _payload: object) -> None:
        self._set_busy_ui(False, is_batch=False)
        self._cleanup_background_task()

    def _cleanup_background_task(self) -> None:
        worker = self._task_worker
        thread = self._task_thread
        self._task_worker = None
        self._task_thread = None
        self._batch_cancel_token = None
        self._is_batch_running = False

        if thread is not None:
            thread.quit()
            thread.wait()
            thread.deleteLater()
        if worker is not None:
            worker.deleteLater()

    def _set_busy_ui(self, is_busy: bool, is_batch: bool) -> None:
        self._is_busy = is_busy
        self._is_batch_running = is_busy and is_batch

        self.input_edit.setReadOnly(is_busy)
        self.resolve_btn.setEnabled(not is_busy)
        self.key_rule_combo.setEnabled(True)
        self.debug_panel.setEnabled(not is_busy)

        # 浏览已完成结果不应被锁死，运行中也允许查看和切换。
        self.pending_table.setEnabled(True)
        self.success_table.setEnabled(True)
        self.failed_table.setEnabled(True)
        self.candidate_table.setEnabled(True)

        self.cancel_btn.setVisible(is_batch or self.cancel_btn.isVisible())
        self.cancel_btn.setEnabled(is_busy and is_batch)
        if not is_busy:
            self.cancel_btn.setVisible(False)

        self._update_action_buttons()

    def _update_progress(self, message: str, step: int, total: int) -> None:
        self.progress_label.setText(message)
        if total <= 0:
            self.progress_bar.setRange(0, 0)
            return
        ratio = max(0.0, min(1.0, step / total))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(ratio * 100))

    def _result_to_row(self, index: int, result: ResolutionResult) -> dict:
        selected = result.selected
        title = selected.title if selected else (result.parsed_title or "")
        authors = selected.authors if selected else result.parsed_authors
        year = selected.year if selected and selected.year is not None else result.parsed_year
        doi = selected.doi if selected else (result.doi or "")
        if not title:
            title = self._fallback_title_from_raw(result.raw_input)
        message = result.message or ("自动检索失败" if result.status == ResultStatus.FAILED else "")
        if not year:
            year = self._fallback_year_from_raw(result.raw_input)
        return {
            "index": index,
            "title": title or "",
            "authors": ", ".join(authors) if authors else "",
            "year": str(year) if year else "",
            "doi": doi or "",
            "message": message,
        }

    @staticmethod
    def _fallback_title_from_raw(raw: str) -> str:
        text = re.sub(r"^\s*(?:\[\d+\]|\d+[.)])\s*", "", raw or "")
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""
        if len(text) <= 120:
            return text
        return f"{text[:120]}..."

    @staticmethod
    def _fallback_year_from_raw(raw: str) -> int | None:
        matches = re.findall(r"\b(?:19|20)\d{2}\b", raw or "")
        if not matches:
            return None
        try:
            return int(matches[-1])
        except Exception:
            return None

    def _refresh_section_tables(self) -> None:
        success_rows: list[dict] = []
        failed_rows: list[dict] = []
        pending_rows: list[dict] = []

        success_count = 0
        failed_count = 0
        pending_count = 0
        cancelled_count = 0

        for index in sorted(self.entry_inputs):
            result = self.entry_results.get(index)
            if result is None:
                continue
            if result.status == ResultStatus.CANCELLED:
                cancelled_count += 1
                continue
            row = self._result_to_row(index, result)
            if result.status == ResultStatus.SUCCESS:
                success_rows.append(row)
                success_count += 1
            elif result.status == ResultStatus.FAILED:
                failed_rows.append(row)
                failed_count += 1
            elif result.status == ResultStatus.PENDING:
                pending_rows.append(row)
                pending_count += 1

        self.pending_table.load_rows(pending_rows)
        self.success_table.load_rows(success_rows)
        self.failed_table.load_rows(failed_rows)

        summary = f"成功 {success_count} 条 | 失败 {failed_count} 条 | 待确认 {pending_count} 条"
        if cancelled_count:
            summary = f"{summary} | 已取消 {cancelled_count} 条"
        self.summary_label.setText(summary)

        self._update_action_buttons()

    def _select_index(self, index: int) -> None:
        # 仅同步详情，不强制在分区表里自动选中，避免破坏选中制。
        self.selected_entry_index = index
        self._render_selected_result()

    def on_result_table_selection(self, source: str) -> None:
        if self._syncing_selection:
            return

        table_map = {
            "pending": self.pending_table,
            "success": self.success_table,
            "failed": self.failed_table,
        }
        source_table = table_map[source]
        selected_index = source_table.selected_index()
        if selected_index is None:
            return

        self._syncing_selection = True
        for name, table in table_map.items():
            if name == source:
                continue
            table.clearSelection()
        self._syncing_selection = False

        self.selected_entry_index = selected_index
        self._render_selected_result()

    def _render_selected_result(self) -> None:
        selected = self._get_selected_result()
        if not selected:
            self._clear_result_detail()
            self._update_action_buttons()
            return

        _, result = selected
        self.raw_input_line.setText(result.raw_input)

        selected_candidate = result.selected
        title = selected_candidate.title if selected_candidate else (result.parsed_title or "")
        authors = selected_candidate.authors if selected_candidate else result.parsed_authors
        year = selected_candidate.year if selected_candidate and selected_candidate.year is not None else result.parsed_year
        doi = selected_candidate.doi if selected_candidate else (result.doi or "")

        self.title_line.setText(title or "")
        self.authors_line.setText(", ".join(authors) if authors else "")
        self.year_line.setText(str(year) if year else "")
        self.doi_line.setText(doi or "")
        self.status_line.setText(result.status.value)
        self.bibtex_edit.setPlainText(result.bibtex or "")

        self.candidate_table.load_candidates(result.candidates)
        self._update_action_buttons()

    def on_candidate_selection_changed(self) -> None:
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        selected = self._get_selected_result()
        has_selected_ref = selected is not None

        can_open_scholar = False
        can_copy = False
        show_candidate_controls = False
        can_confirm_selected = False
        can_confirm_all = False

        if selected:
            _, result = selected
            can_open_scholar = result.status in {ResultStatus.PENDING, ResultStatus.FAILED} and bool(result.scholar_url)
            can_copy = result.status == ResultStatus.SUCCESS and bool(result.bibtex)
            show_candidate_controls = result.status == ResultStatus.PENDING and len(result.candidates) > 0
            can_confirm_all = show_candidate_controls

            selected_candidate = self.candidate_table.selected_candidate()
            can_confirm_selected = show_candidate_controls and selected_candidate is not None

        # 去重策略：待确认且有候选时，仅展示“打开当前候选”。
        show_general_scholar = has_selected_ref and can_open_scholar and not show_candidate_controls
        self.scholar_btn.setVisible(show_general_scholar)
        self.scholar_btn.setEnabled(show_general_scholar)
        self.copy_btn.setEnabled(has_selected_ref and can_copy)

        self.confirm_btn.setVisible(show_candidate_controls)
        self.confirm_all_btn.setVisible(show_candidate_controls)
        self.candidate_scholar_btn.setVisible(show_candidate_controls)

        self.confirm_btn.setEnabled(can_confirm_selected and not self._is_busy)
        self.confirm_all_btn.setEnabled(can_confirm_all and not self._is_busy)
        self.candidate_scholar_btn.setEnabled(show_candidate_controls and self.candidate_table.selected_candidate() is not None)

        success_bibtex = [
            result.bibtex
            for _, result in sorted(self.entry_results.items())
            if result is not None and result.status == ResultStatus.SUCCESS and bool(result.bibtex)
        ]
        self.copy_all_btn.setEnabled(bool(success_bibtex))

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

    def on_scholar_clicked(self) -> None:
        selected = self._get_selected_result()
        if not selected:
            return
        _, result = selected
        if result.scholar_url:
            QDesktopServices.openUrl(QUrl(result.scholar_url))

    def on_copy_clicked(self) -> None:
        selected = self._get_selected_result()
        if not selected:
            return
        _, result = selected
        text = (result.bibtex or "").strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "复制成功", "BibTeX 已复制到剪贴板")

    def on_copy_all_success_clicked(self) -> None:
        blocks: list[str] = []
        for index in sorted(self.entry_inputs):
            result = self.entry_results.get(index)
            if result is None or result.status != ResultStatus.SUCCESS:
                continue
            text = (result.bibtex or "").strip()
            if text:
                blocks.append(text)
        if not blocks:
            QMessageBox.information(self, "无可复制内容", "当前没有成功条目的 BibTeX")
            return
        QApplication.clipboard().setText("\n\n".join(blocks))
        QMessageBox.information(self, "复制成功", "已复制全部成功条目的 BibTeX")

    def on_key_rule_changed(self) -> None:
        rule = self.current_key_rule()
        for index in sorted(self.entry_results):
            result = self.entry_results.get(index)
            if result is None:
                continue
            if result.status != ResultStatus.SUCCESS:
                continue
            if index in self.bulk_confirmed_candidates:
                result.bibtex = self._build_bulk_bibtex(index, rule)
                self.entry_results[index] = result
                continue
            self.entry_results[index] = self.resolver.rebuild_result_bibtex(result, rule)

        self._refresh_section_tables()
        self._render_selected_result()

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

    def _build_bulk_bibtex(self, entry_index: int, key_rule: BibKeyRule) -> str:
        blocks: list[str] = []
        for candidate, base_bibtex in self.bulk_confirmed_candidates.get(entry_index, []):
            bibtex, _ = build_bibtex_for_candidate(candidate, key_rule, base_bibtex)
            if bibtex.strip():
                blocks.append(bibtex.strip())
        return "\n\n".join(blocks)
