from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InputKind(str, Enum):
    DOI = "doi"
    TITLE = "title"
    REFERENCE = "reference"


class ResultStatus(str, Enum):
    SUCCESS = "成功"
    PENDING = "待确认"
    FAILED = "失败"
    CANCELLED = "已取消"


class BibKeyRule(str, Enum):
    AUTHOR_YEAR = "author_year"
    AUTHOR_YEAR_TITLE = "author_year_title"
    TITLE_YEAR = "title_year"


class SplitReasonCode(str, Enum):
    OK = "ok"
    AMBIGUOUS_MULTI = "ambiguous_multi"
    AMBIGUOUS_SINGLE = "ambiguous_single"
    EMPTY_INPUT = "empty_input"
    TOO_SHORT = "too_short"


class BatchProgressStage(str, Enum):
    BATCH_START = "batch_start"
    ITEM_START = "item_start"
    ITEM_DONE = "item_done"
    ITEM_FAILED = "item_failed"
    ITEM_CANCELLED = "item_cancelled"
    BATCH_DONE = "batch_done"


@dataclass(slots=True)
class ParsedReference:
    raw_input: str
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None


@dataclass(slots=True)
class CandidateRecord:
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    source: str
    raw: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    title_score: float = 0.0
    year_score: float = 0.0
    author_score: float = 0.0


@dataclass(slots=True)
class BatchSplitResult:
    items: list[str] = field(default_factory=list)
    is_ambiguous: bool = False
    ambiguous_indexes: list[int] = field(default_factory=list)
    reason_code: SplitReasonCode = SplitReasonCode.OK


@dataclass(slots=True)
class ResolutionResult:
    raw_input: str
    input_kind: InputKind
    status: ResultStatus
    parsed_title: str | None = None
    parsed_authors: list[str] = field(default_factory=list)
    parsed_year: int | None = None
    selected: CandidateRecord | None = None
    candidates: list[CandidateRecord] = field(default_factory=list)
    doi: str | None = None
    bibtex: str | None = None
    bibtex_base: str | None = None
    scholar_url: str | None = None
    message: str = ""


@dataclass(slots=True)
class BatchProgressEvent:
    index: int
    total: int
    stage: BatchProgressStage
    message: str
    result: ResolutionResult | None = None
