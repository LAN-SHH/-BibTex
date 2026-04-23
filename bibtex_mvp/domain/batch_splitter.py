from __future__ import annotations

import re

from .input_classifier import YEAR_PATTERN, extract_doi
from .models import BatchSplitResult, SplitReasonCode

NUMBERED_MARKER_PATTERN = re.compile(r"(?m)^\s*(?:\[\d+\]|\d+[.)])\s+")
AUTHOR_START_PATTERN = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ'`-]+(?:,\s*[A-Z]\.)")
ORG_START_PATTERN = re.compile(r"^[A-Z][A-Za-z&.\-\s]{2,}\.\s*\((19|20)\d{2}\)")


def _normalize_line(line: str) -> str:
    line = line.replace("\u3000", " ").strip()
    line = re.sub(r"\s+", " ", line)
    return line


def _effective_length(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9\u4e00-\u9fff]", text))


def _token_count(text: str) -> int:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text, flags=re.UNICODE)
    tokens = [t for t in normalized.split() if t]
    return len(tokens)


def is_too_short(text: str) -> bool:
    if extract_doi(text):
        return False
    if YEAR_PATTERN.search(text):
        return False
    return _effective_length(text) < 20 and _token_count(text) < 4


def _looks_like_reference_entry(text: str) -> bool:
    content = _normalize_line(text)
    if not content:
        return False
    if extract_doi(content):
        return True
    if YEAR_PATTERN.search(content):
        return _effective_length(content) >= 20
    return False


def _looks_like_new_entry_start(line: str) -> bool:
    chunk = _normalize_line(line)
    if not chunk:
        return False
    return bool(
        AUTHOR_START_PATTERN.search(chunk)
        or ORG_START_PATTERN.search(chunk)
        or NUMBERED_MARKER_PATTERN.search(chunk)
    )


def _looks_like_entry_complete(line: str) -> bool:
    chunk = _normalize_line(line)
    if extract_doi(chunk):
        return True
    if YEAR_PATTERN.search(chunk) and chunk.endswith("."):
        return True
    if YEAR_PATTERN.search(chunk) and re.search(r"\b\d+\(\d+\)|\d+\s*[-–]\s*\d+", chunk):
        return True
    return False


def _split_by_blank_lines(text: str) -> list[str]:
    blocks = [block for block in re.split(r"\n\s*\n+", text) if block.strip()]
    return [_normalize_line(block) for block in blocks if _normalize_line(block)]


def _split_by_numbered_markers(text: str) -> list[str]:
    matches = list(NUMBERED_MARKER_PATTERN.finditer(text))
    if len(matches) < 2:
        return []
    items: list[str] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        part = _normalize_line(text[start:end])
        if part:
            items.append(part)
    return items


def _split_by_lines_with_merge(text: str) -> list[str]:
    lines = [_normalize_line(v) for v in text.splitlines() if _normalize_line(v)]
    if len(lines) <= 1:
        return lines
    items: list[str] = []
    current = lines[0]
    for line in lines[1:]:
        if _looks_like_new_entry_start(line) and _looks_like_entry_complete(current):
            items.append(_normalize_line(current))
            current = line
            continue
        current = _normalize_line(f"{current} {line}")
    if current:
        items.append(_normalize_line(current))
    return items


def _has_multi_reference_signal(text: str) -> bool:
    year_count = len(YEAR_PATTERN.findall(text))
    doi_count = len(re.findall(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, flags=re.IGNORECASE))
    non_empty_lines = len([line for line in text.splitlines() if line.strip()])
    return year_count >= 2 or doi_count >= 2 or non_empty_lines >= 3


def _build_ambiguous_multi(items: list[str], indexes: list[int]) -> BatchSplitResult:
    return BatchSplitResult(
        items=items,
        is_ambiguous=True,
        ambiguous_indexes=indexes,
        reason_code=SplitReasonCode.AMBIGUOUS_MULTI,
    )


def split_batch_input(raw_text: str) -> BatchSplitResult:
    text = (raw_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return BatchSplitResult(reason_code=SplitReasonCode.EMPTY_INPUT)

    blank_items = _split_by_blank_lines(text)
    numbered_items = _split_by_numbered_markers(text)
    line_items = _split_by_lines_with_merge(text)

    items: list[str]
    if len(blank_items) >= 2:
        items = blank_items
    elif len(numbered_items) >= 2:
        items = numbered_items
    elif len(line_items) >= 2:
        items = line_items
    else:
        items = [_normalize_line(text)]

    items = [item for item in items if item]
    if not items:
        return BatchSplitResult(reason_code=SplitReasonCode.EMPTY_INPUT)

    if len(items) == 1:
        one = items[0]
        if is_too_short(one):
            return BatchSplitResult(
                items=items,
                is_ambiguous=True,
                ambiguous_indexes=[1],
                reason_code=SplitReasonCode.TOO_SHORT,
            )
        if _has_multi_reference_signal(text):
            return BatchSplitResult(
                items=items,
                is_ambiguous=True,
                ambiguous_indexes=[1],
                reason_code=SplitReasonCode.AMBIGUOUS_SINGLE,
            )
        return BatchSplitResult(items=items, reason_code=SplitReasonCode.OK)

    ambiguous_indexes: list[int] = []
    for idx, item in enumerate(items, start=1):
        if not _looks_like_reference_entry(item):
            ambiguous_indexes.append(idx)

    if ambiguous_indexes:
        return _build_ambiguous_multi(items, ambiguous_indexes)
    return BatchSplitResult(items=items, reason_code=SplitReasonCode.OK)

