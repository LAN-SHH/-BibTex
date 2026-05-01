from __future__ import annotations

import asyncio
import re
from typing import Awaitable, Callable

from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QFontMetrics, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from bibtex_mvp.application.orchestrator import BatchCancelToken, ResolverConfig
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


class KeyRuleComboBox(QComboBox):
    def __init__(self) -> None:
        super().__init__()
        view = QListView(self)
        view.setFrameShape(QFrame.Shape.NoFrame)
        view.setMouseTracking(True)
        view.setUniformItemSizes(True)
        view.setObjectName("KeyRuleComboView")
        self.setView(view)
        self.setMaxVisibleItems(6)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        # Avoid accidental key-rule switching when users scroll the page.
        if self.hasFocus():
            super().wheelEvent(event)
            return
        event.ignore()

    def showPopup(self) -> None:  # noqa: N802
        self.view().scrollToTop()
        super().showPopup()


class MainWindow(QMainWindow):
    def __init__(
        self,
        auto_accept_threshold: float = 0.92,
        candidate_floor_threshold: float = 0.80,
    ) -> None:
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
        self.setWindowFlag(Qt.WindowType.MSWindowsFixedSizeDialogHint, False)
        self.setMaximumSize(16777215, 16777215)
        self.setMinimumSize(980, 780)
        self.setWindowTitle("参考文献转 BibTeX")
        self.resize(1320, 920)
        self.resolver = SingleEntryResolver()
        self.auto_accept_threshold = auto_accept_threshold
        self.candidate_floor_threshold = candidate_floor_threshold

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
        self._action_widgets: list[QWidget] = []
        self._last_window_height: int = 0

        self._build_ui()
        self._apply_theme()
        self._apply_min_width_for_candidate_hint()
        self._apply_responsive_heights()
        self._last_window_height = self.height()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("RootPanel")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header_card = QWidget()
        header_card.setObjectName("HeaderCard")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(10)

        header_text_layout = QVBoxLayout()
        header_text_layout.setContentsMargins(0, 0, 0, 0)
        header_text_layout.setSpacing(2)

        title_label = QLabel("参考文献整理为 BibTeX")
        title_label.setObjectName("PageTitle")
        desc_label = QLabel("面向学术批量整理场景，支持自动处理、状态分流、人工确认与 BibTeX 导出。")
        desc_label.setObjectName("PageHint")

        header_text_layout.addWidget(title_label)
        header_text_layout.addWidget(desc_label)
        header_layout.addLayout(header_text_layout, 1)

        mode_badge = QLabel("学术工作台")
        mode_badge.setObjectName("ModeBadge")
        header_layout.addWidget(mode_badge, 0, Qt.AlignmentFlag.AlignTop)
        root_layout.addWidget(header_card)

        flow_card = QWidget()
        flow_card.setObjectName("FlowCard")
        flow_layout = QHBoxLayout(flow_card)
        flow_layout.setContentsMargins(14, 10, 14, 10)
        flow_layout.setSpacing(8)

        flow_steps = ["输入参考文献", "自动处理", "查看状态", "人工确认", "导出 BibTeX"]
        for idx, step in enumerate(flow_steps):
            step_label = QLabel(step)
            step_label.setObjectName("FlowStep")
            flow_layout.addWidget(step_label)
            if idx != len(flow_steps) - 1:
                arrow = QLabel("→")
                arrow.setObjectName("FlowArrow")
                flow_layout.addWidget(arrow)
        flow_layout.addStretch(1)
        root_layout.addWidget(flow_card)

        input_group = QGroupBox("输入区")
        input_layout = QVBoxLayout(input_group)
        input_layout.setContentsMargins(12, 12, 12, 12)
        input_layout.setSpacing(8)

        input_hint = QLabel("支持 DOI、标题或完整参考文献。可直接批量粘贴，程序会先尝试自动分条。")
        input_hint.setObjectName("SectionHint")
        input_layout.addWidget(input_hint)

        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("请粘贴一条或多条参考文献，按原始格式输入即可。")
        self.input_edit.setMinimumHeight(120)
        self.input_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        input_layout.addWidget(self.input_edit, 1)
        self.action_bar_widget = QWidget()
        self.action_bar_widget.setObjectName("ActionCard")
        self.action_bar_layout = QGridLayout()
        self.action_bar_layout.setContentsMargins(12, 10, 12, 10)
        self.action_bar_layout.setHorizontalSpacing(8)
        self.action_bar_layout.setVerticalSpacing(8)
        self.action_bar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.action_bar_widget.setLayout(self.action_bar_layout)
        root_layout.addWidget(self.action_bar_widget)

        self.resolve_btn = QPushButton("开始处理")
        self.resolve_btn.clicked.connect(self.on_resolve_clicked)
        self._action_widgets.append(self.resolve_btn)

        self.cancel_btn = QPushButton("取消批量任务")
        self.cancel_btn.clicked.connect(self.on_cancel_batch_clicked)
        self.cancel_btn.setEnabled(False)
        self._action_widgets.append(self.cancel_btn)

        self.confirm_btn = QPushButton("确认当前候选")
        self.confirm_btn.clicked.connect(self.on_confirm_candidate_clicked)
        self.confirm_btn.setVisible(False)
        self.confirm_btn.setEnabled(False)
        self._action_widgets.append(self.confirm_btn)

        self.confirm_all_btn = QPushButton("确认全部候选")
        self.confirm_all_btn.clicked.connect(self.on_confirm_all_candidates_clicked)
        self.confirm_all_btn.setVisible(False)
        self.confirm_all_btn.setEnabled(False)
        self._action_widgets.append(self.confirm_all_btn)

        self.candidate_scholar_btn = QPushButton("在 Scholar 打开当前候选")
        self.candidate_scholar_btn.clicked.connect(self.on_open_candidate_scholar_clicked)
        self.candidate_scholar_btn.setVisible(False)
        self.candidate_scholar_btn.setEnabled(False)
        self._action_widgets.append(self.candidate_scholar_btn)

        self.scholar_btn = QPushButton("在 Scholar 打开选中文献")
        self.scholar_btn.clicked.connect(self.on_scholar_clicked)
        self.scholar_btn.setVisible(False)
        self.scholar_btn.setEnabled(False)
        self._action_widgets.append(self.scholar_btn)

        self.copy_btn = QPushButton("复制当前 BibTeX")
        self.copy_btn.clicked.connect(self.on_copy_clicked)
        self.copy_btn.setEnabled(False)
        self._action_widgets.append(self.copy_btn)

        self.copy_all_btn = QPushButton("复制全部成功 BibTeX")
        self.copy_all_btn.clicked.connect(self.on_copy_all_success_clicked)
        self.copy_all_btn.setEnabled(False)
        self._action_widgets.append(self.copy_all_btn)

        self.key_rule_combo = KeyRuleComboBox()
        self.key_rule_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.key_rule_combo.setMinimumContentsLength(30)
        self.key_rule_combo.setMinimumWidth(340)
        self.key_rule_combo.setMinimumHeight(34)
        self.key_rule_combo.addItem("作者姓 + 年份，例如 Zhou2007", BibKeyRule.AUTHOR_YEAR)
        self.key_rule_combo.addItem("作者姓 + 年份 + 标题首词，例如 Zhou2007Functional", BibKeyRule.AUTHOR_YEAR_TITLE)
        self.key_rule_combo.addItem("标题首词 + 年份，例如 Functional2007", BibKeyRule.TITLE_YEAR)
        self.key_rule_combo.currentIndexChanged.connect(self.on_key_rule_changed)
        self._action_widgets.append(self.key_rule_combo)
        self._relayout_action_bar()

        progress_card = QWidget()
        progress_card.setObjectName("ProgressCard")
        progress_layout = QHBoxLayout(progress_card)
        progress_layout.setContentsMargins(12, 10, 12, 10)
        progress_layout.setSpacing(10)

        self.progress_label = QLabel("就绪")
        self.progress_label.setObjectName("ProgressLabel")
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar, 1)

        self.summary_label = QLabel("成功 0 条 | 失败 0 条 | 待确认 0 条")
        self.summary_label.setObjectName("SummaryLabel")
        progress_layout.addWidget(self.summary_label)
        root_layout.addWidget(progress_card)

        result_group = QGroupBox("处理结果")
        result_layout = QVBoxLayout(result_group)
        result_layout.setContentsMargins(12, 12, 12, 12)
        result_layout.setSpacing(10)

        sections_layout = QHBoxLayout()
        sections_layout.setSpacing(12)
        result_layout.addLayout(sections_layout)

        success_group = QGroupBox("成功")
        success_group.setMinimumWidth(300)
        success_layout = QVBoxLayout(success_group)
        success_layout.setContentsMargins(8, 10, 8, 8)
        self.success_table = ResultTable()
        self.success_table.setMinimumHeight(120)
        self.success_table.itemSelectionChanged.connect(lambda: self.on_result_table_selection("success"))
        success_layout.addWidget(self.success_table)
        sections_layout.addWidget(success_group, 1)

        pending_group = QGroupBox("待确认")
        pending_group.setMinimumWidth(300)
        pending_layout = QVBoxLayout(pending_group)
        pending_layout.setContentsMargins(8, 10, 8, 8)
        self.pending_table = ResultTable()
        self.pending_table.setMinimumHeight(120)
        self.pending_table.itemSelectionChanged.connect(lambda: self.on_result_table_selection("pending"))
        pending_layout.addWidget(self.pending_table)
        sections_layout.addWidget(pending_group, 1)

        failed_group = QGroupBox("失败")
        failed_group.setMinimumWidth(300)
        failed_layout = QVBoxLayout(failed_group)
        failed_layout.setContentsMargins(8, 10, 8, 8)
        self.failed_table = ResultTable()
        self.failed_table.setMinimumHeight(120)
        self.failed_table.itemSelectionChanged.connect(lambda: self.on_result_table_selection("failed"))
        failed_layout.addWidget(self.failed_table)
        sections_layout.addWidget(failed_group, 1)
        lower_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.lower_splitter = lower_splitter
        lower_splitter.setChildrenCollapsible(False)
        lower_splitter.setHandleWidth(8)

        detail_panel = QWidget()
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(10)

        bib_group = QGroupBox("BibTeX 输出")
        self.bib_group = bib_group
        bib_layout = QVBoxLayout(bib_group)
        bib_layout.setContentsMargins(8, 10, 8, 8)

        self.bibtex_edit = QPlainTextEdit()
        self.bibtex_edit.setReadOnly(True)
        self.bibtex_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.bibtex_edit.setMinimumHeight(140)
        self.bibtex_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        bib_layout.addWidget(self.bibtex_edit)

        detail_layout.addWidget(bib_group, 1)
        lower_splitter.addWidget(detail_panel)

        candidate_panel = QWidget()
        candidate_layout = QVBoxLayout(candidate_panel)
        candidate_layout.setContentsMargins(0, 0, 0, 0)
        candidate_layout.setSpacing(10)

        candidate_group = QGroupBox("候选确认区")
        self.candidate_group = candidate_group
        candidate_group_layout = QVBoxLayout(candidate_group)
        candidate_group_layout.setContentsMargins(8, 8, 8, 12)
        candidate_group_layout.setSpacing(6)
        candidate_hint = QLabel("待确认条目会在这里展示候选结果。可查看候选、跳转 Scholar，再决定确认哪一条。")
        self.candidate_hint_label = candidate_hint
        candidate_hint.setObjectName("SectionHint")
        candidate_hint.setWordWrap(True)
        candidate_hint.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        candidate_hint.setMaximumHeight(36)
        candidate_group_layout.addWidget(candidate_hint)

        self.candidate_table = CandidateTable()
        self.candidate_table.setMinimumHeight(170)
        self.candidate_table.itemSelectionChanged.connect(self.on_candidate_selection_changed)
        self.candidate_table.cellDoubleClicked.connect(self.on_candidate_row_double_clicked)
        candidate_group_layout.addWidget(self.candidate_table, 1)

        candidate_layout.addWidget(candidate_group, 1)
        lower_splitter.addWidget(candidate_panel)
        lower_splitter.setStretchFactor(0, 1)
        lower_splitter.setStretchFactor(1, 1)
        lower_splitter.setSizes([620, 620])

        content_splitter = QSplitter(Qt.Orientation.Vertical)
        self.content_splitter = content_splitter
        content_splitter.setChildrenCollapsible(False)
        content_splitter.setHandleWidth(8)
        content_splitter.addWidget(input_group)
        content_splitter.addWidget(result_group)
        content_splitter.addWidget(lower_splitter)
        content_splitter.setStretchFactor(0, 2)
        content_splitter.setStretchFactor(1, 3)
        content_splitter.setStretchFactor(2, 4)
        content_splitter.setSizes([210, 280, 360])
        root_layout.addWidget(content_splitter, 1)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget#RootPanel {
                background: #eef2f7;
            }
            QWidget#HeaderCard {
                background: #ffffff;
                border: 1px solid #d8e1ef;
                border-radius: 12px;
            }
            QWidget#FlowCard,
            QWidget#ActionCard,
            QWidget#ProgressCard {
                background: #ffffff;
                border: 1px solid #d8e1ef;
                border-radius: 12px;
            }
            QLabel {
                color: #18263d;
            }
            QLabel#PageTitle {
                font-size: 24px;
                font-weight: 700;
                color: #13233c;
            }
            QLabel#PageHint {
                color: #4b5d79;
                font-size: 13px;
            }
            QLabel#ModeBadge {
                background: #e7eefb;
                color: #1b3d77;
                border: 1px solid #ccdaf2;
                border-radius: 11px;
                padding: 3px 10px;
                font-weight: 600;
            }
            QLabel#FlowStep {
                color: #1d3557;
                background: #f6f9ff;
                border: 1px solid #d7e3f8;
                border-radius: 8px;
                padding: 4px 10px;
                font-weight: 600;
            }
            QLabel#FlowArrow {
                color: #7a8faa;
                font-size: 15px;
                font-weight: 600;
                padding: 0 2px;
            }
            QLabel#SectionHint {
                color: #607089;
                font-size: 12px;
            }
            QLabel#ProgressLabel {
                color: #1e3558;
                font-weight: 600;
            }
            QLabel#SummaryLabel {
                color: #445a77;
                font-weight: 500;
            }
            QDialog, QMessageBox {
                background: #f3f7fb;
                color: #1a2436;
            }
            QDialog {
                border: 1px solid #dbe4f3;
                border-radius: 10px;
            }
            QDialog QLabel, QMessageBox QLabel {
                color: #1a2436;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #dbe4f3;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 8px;
                color: #163052;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background: #ecf3ff;
                color: #142847;
                border: 1px solid #cfddf4;
                border-radius: 8px;
                padding: 7px 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #deebff;
                border: 1px solid #b8cdef;
            }
            QPushButton:pressed {
                background: #ccdfff;
                border: 1px solid #9ab7e4;
            }
            QPushButton:disabled {
                background: #dce2ec;
                color: #77849b;
                border: 1px solid #d1d9e4;
            }
            QLineEdit, QPlainTextEdit, QComboBox {
                background: #ffffff;
                border: 1px solid #c7d3e8;
                border-radius: 8px;
                padding: 5px 7px;
                color: #101b2e;
                selection-background-color: #cddfff;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
                border: 1px solid #8aa9e6;
            }
            QComboBox {
                min-height: 32px;
                padding: 4px 24px 4px 8px;
                combobox-popup: 0;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border: none;
                background: transparent;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #111827;
                border: 1px solid #c7d3e8;
                border-radius: 8px;
                selection-background-color: #dce9ff;
                selection-color: #0f1e3a;
                outline: 0;
                padding: 3px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
                padding: 4px 8px;
                border-radius: 6px;
                margin: 1px 0;
            }
            QComboBox QAbstractItemView::item:hover {
                background: #dce9ff;
                color: #0f1e3a;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #c8dcff;
                color: #0f1e3a;
            }
            QFrame#QComboBoxPrivateContainer {
                background: #ffffff;
                border: 1px solid #c7d3e8;
                border-radius: 8px;
            }
            QFrame#QComboBoxPrivateContainer QAbstractItemView {
                border: none;
                margin: 0;
            }
            QTableWidget, QTableView {
                background: #ffffff;
                color: #101b2e;
                border: 1px solid #d1dbeb;
                border-radius: 8px;
                gridline-color: #e1e8f3;
                selection-background-color: #dce9ff;
                selection-color: #0f1e3a;
                alternate-background-color: #f8fbff;
            }
            QTableWidget::item, QTableView::item {
                background: #ffffff;
                color: #101b2e;
            }
            QHeaderView::section {
                background: #f4f7fc;
                color: #1a2e4d;
                border: 1px solid #d9e1ef;
                padding: 6px;
                font-weight: 700;
            }
            QProgressBar {
                background: #ffffff;
                color: #0f1e3a;
                border: 1px solid #c7d3e8;
                border-radius: 6px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #2d5fcc;
                border-radius: 6px;
            }
            QSplitter::handle {
                background: #d8e1ef;
                border-radius: 4px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 2px 0 2px 0;
            }
            QScrollBar::handle:vertical {
                background: #c9d7f0;
                min-height: 26px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #aebfdd;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: transparent;
                border: none;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 6px;
                margin: 0 2px 0 2px;
            }
            QScrollBar::handle:horizontal {
                background: #c9d7f0;
                min-width: 26px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #aebfdd;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
                background: transparent;
                border: none;
            }
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                background: transparent;
            }
            QAbstractScrollArea::corner {
                background: transparent;
                border: none;
            }
            """
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout_action_bar()
        current_h = self.height()
        if current_h != self._last_window_height:
            self._apply_responsive_heights()
            self._last_window_height = current_h

    def _apply_responsive_heights(self) -> None:
        h = max(520, self.height())
        input_h = max(72, min(140, int(h * 0.10)))
        result_table_h = max(64, min(140, int(h * 0.09)))
        detail_table_h = max(92, min(220, int(h * 0.13)))

        self.input_edit.setMinimumHeight(input_h)
        self.success_table.setMinimumHeight(result_table_h)
        self.pending_table.setMinimumHeight(result_table_h)
        self.failed_table.setMinimumHeight(result_table_h)
        self.bibtex_edit.setMinimumHeight(detail_table_h)
        self.candidate_table.setMinimumHeight(detail_table_h)
        self.bib_group.setMinimumHeight(detail_table_h + 36)
        self.candidate_group.setMinimumHeight(detail_table_h + 56)

        # Keep vertical splitter ratios stable. Horizontal resizing should not
        # force-reset these sizes, otherwise lower panes get compressed.

    def _apply_min_width_for_candidate_hint(self) -> None:
        text = self.candidate_hint_label.text()
        text_width = QFontMetrics(self.candidate_hint_label.font()).horizontalAdvance(text)
        hint_required_width = text_width + 6
        self.candidate_hint_label.setMinimumWidth(hint_required_width)

        # Window width budget
        # left+right root margins(32) + splitter handle(8) + two half panels + safety(24)
        required_window_width = hint_required_width * 2 + 64
        required_window_width = max(980, required_window_width)
        self.setMinimumWidth(required_window_width)

    def _relayout_action_bar(self) -> None:
        if not hasattr(self, "action_bar_layout"):
            return

        while self.action_bar_layout.count():
            _ = self.action_bar_layout.takeAt(0)

        visible_widgets = [w for w in self._action_widgets if not w.isHidden()]
        self.action_bar_widget.setVisible(True)
        if not visible_widgets:
            visible_widgets = [self.resolve_btn, self.cancel_btn, self.copy_btn, self.copy_all_btn, self.key_rule_combo]

        available_width = self.action_bar_widget.contentsRect().width()
        if available_width <= 0:
            available_width = max(640, self.width() - 80)
        spacing = max(0, self.action_bar_layout.horizontalSpacing())

        # Prefer one row. Reflow only when one full row cannot fit.
        total_required = 0
        for idx, widget in enumerate(visible_widgets):
            width = max(widget.minimumSizeHint().width(), widget.sizeHint().width())
            total_required += width
            if idx > 0:
                total_required += spacing

        if total_required <= available_width:
            for col, widget in enumerate(visible_widgets):
                self.action_bar_layout.addWidget(widget, 0, col)
            return

        row = 0
        col = 0
        used = 0
        for widget in visible_widgets:
            target = max(widget.minimumSizeHint().width(), widget.sizeHint().width())
            if col > 0 and used + spacing + target > available_width:
                row += 1
                col = 0
                used = 0
            self.action_bar_layout.addWidget(widget, row, col)
            if col == 0:
                used = target
            else:
                used += spacing + target
            col += 1

    def current_key_rule(self) -> BibKeyRule:
        return self.key_rule_combo.currentData()

    def _resolver_config(self) -> ResolverConfig:
        return ResolverConfig(
            auto_accept_threshold=self.auto_accept_threshold,
            candidate_floor_threshold=self.candidate_floor_threshold,
            max_rows=20,
        )

    def _normalize_entry(self, value: str) -> str:
        value = (value or "").replace("\u3000", " ").strip()
        value = " ".join(value.split())
        return value

    def _clear_result_detail(self) -> None:
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
            QMessageBox.warning(self, "输入为空", "请先输入参考文献内容。")
            return None

        items = [self._normalize_entry(item) for item in split_result.items if self._normalize_entry(item)]
        if not items:
            QMessageBox.warning(self, "输入为空", "请先输入参考文献内容。")
            return None

        if split_result.is_ambiguous and len(items) >= 2:
            dialog = AmbiguousSplitDialog(items=items, ambiguous_indexes=split_result.ambiguous_indexes, parent=self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            items = [self._normalize_entry(item) for item in dialog.merged_items() if self._normalize_entry(item)]
            if not items:
                QMessageBox.warning(self, "分条为空", "分条结果为空，请重新编辑后再继续。")
                return None
            return items

        if split_result.is_ambiguous and len(items) == 1:
            return self._handle_single_ambiguous_choice(items[0], split_result.reason_code)

        return items

    def _handle_single_ambiguous_choice(self, item: str, reason_code: SplitReasonCode) -> list[str] | None:
        content = "程序暂时无法可靠分条，请选择下一步操作。"
        if reason_code == SplitReasonCode.TOO_SHORT:
            content = "输入内容过短，无法可靠分条，请选择下一步操作。"

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
            QMessageBox.warning(self, "输入为空", "请先输入 DOI、标题或完整参考文献。")
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
        config = self._resolver_config()

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
        config = self._resolver_config()
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
        # 浏览已完成结果不应被锁死，运行中也允许查看和切换。
        self.pending_table.setEnabled(True)
        self.success_table.setEnabled(True)
        self.failed_table.setEnabled(True)
        self.candidate_table.setEnabled(True)

        self.cancel_btn.setEnabled(is_busy and is_batch)

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

        show_confirm_current = show_candidate_controls and self.candidate_table.selected_candidate() is not None
        self.confirm_btn.setVisible(show_confirm_current)
        self.confirm_all_btn.setVisible(show_candidate_controls)
        self.candidate_scholar_btn.setVisible(show_confirm_current)

        self.confirm_btn.setEnabled(show_confirm_current and can_confirm_selected and not self._is_busy)
        self.confirm_all_btn.setEnabled(show_candidate_controls and can_confirm_all and not self._is_busy)
        self.candidate_scholar_btn.setEnabled(show_confirm_current)

        success_bibtex = [
            result.bibtex
            for _, result in sorted(self.entry_results.items())
            if result is not None and result.status == ResultStatus.SUCCESS and bool(result.bibtex)
        ]
        self.copy_all_btn.setEnabled(bool(success_bibtex))
        self._relayout_action_bar()

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
            return

        # For success items or records without prebuilt scholar_url, build a query from current result.
        title = result.parsed_title or ""
        authors = result.parsed_authors or []
        year = result.parsed_year
        if result.selected is not None:
            title = result.selected.title or title
            authors = result.selected.authors or authors
            year = result.selected.year or year

        parts: list[str] = []
        if title:
            parts.append(title)
        if authors:
            parts.append(authors[0].split(",", 1)[0].strip())
        if year:
            parts.append(str(year))
        if not parts and result.raw_input:
            parts.append(result.raw_input)
        if not parts:
            return

        url = build_scholar_search_url(" ".join(parts))
        QDesktopServices.openUrl(QUrl(url))

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
