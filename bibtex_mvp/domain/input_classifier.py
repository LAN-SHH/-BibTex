from __future__ import annotations

import re

from .models import InputKind

DOI_PATTERN = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"(19|20)\d{2}")


def normalize_text(value: str) -> str:
    value = value.strip()
    value = value.replace("\u3000", " ")
    value = re.sub(r"\s+", " ", value)
    return value


def extract_doi(value: str) -> str | None:
    match = DOI_PATTERN.search(value or "")
    if not match:
        return None
    doi = match.group(1).strip().rstrip(").,;")
    return doi.lower()


def looks_like_reference(value: str) -> bool:
    text = normalize_text(value)
    if len(text) < 30:
        return False
    has_year = bool(YEAR_PATTERN.search(text))
    has_author_hint = bool(re.search(r"[A-Za-z]+\s*,\s*[A-Z]\.", text))
    has_journal_hint = bool(re.search(r"\d+\(\d+\)|\d+\s*[-–]\s*\d+", text))
    has_multiple_separators = text.count(",") >= 3 and "." in text
    return has_year and (has_author_hint or has_journal_hint or has_multiple_separators)


def classify_input(value: str) -> InputKind:
    text = normalize_text(value)
    if extract_doi(text):
        return InputKind.DOI
    if looks_like_reference(text):
        return InputKind.REFERENCE
    return InputKind.TITLE

