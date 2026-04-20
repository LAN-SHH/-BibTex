from __future__ import annotations

import re

from .models import InputKind

DOI_PATTERN = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


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
    if not has_year:
        return False

    has_apa_author_hint = bool(re.search(r"[A-Za-z]+\s*,\s*[A-Z]\.", text))
    has_org_author_hint = bool(re.search(r"^[A-Za-z][A-Za-z&.\-\s]{3,}\.\s*\((19|20)\d{2}\)", text))
    has_vancouver_author_hint = bool(
        re.search(
            r"^[A-Za-zÀ-ÖØ-öø-ÿ'`-]+\s+[A-Z]{1,5}(?:,\s*[A-Za-zÀ-ÖØ-öø-ÿ'`-]+\s+[A-Z]{1,5})+",
            text,
        )
    )
    has_journal_hint = bool(re.search(r"\d+\(\d+\)|\d+\s*[-–]\s*\d+", text))
    has_reference_shape = text.count(".") >= 2 and text.count(",") >= 1

    return bool(
        has_apa_author_hint
        or has_org_author_hint
        or has_vancouver_author_hint
        or has_journal_hint
        or has_reference_shape
    )


def classify_input(value: str) -> InputKind:
    text = normalize_text(value)
    if extract_doi(text):
        return InputKind.DOI
    if looks_like_reference(text):
        return InputKind.REFERENCE
    return InputKind.TITLE

