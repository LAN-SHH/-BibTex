from __future__ import annotations

import re

from .input_classifier import extract_doi, normalize_text
from .models import ParsedReference

YEAR_BRACKET_PATTERN = re.compile(r"\((19|20)\d{2}[a-z]?\)")
YEAR_PATTERN = re.compile(r"(19|20)\d{2}")
AUTHOR_PATTERN = re.compile(r"([A-Za-zÀ-ÖØ-öø-ÿ'`-]+,\s*(?:[A-Z]\.\s*)+)")


def _extract_year(text: str) -> tuple[int | None, tuple[int, int] | None]:
    bracket_match = YEAR_BRACKET_PATTERN.search(text)
    if bracket_match:
        year = int(re.search(r"(19|20)\d{2}", bracket_match.group(0)).group(0))
        return year, bracket_match.span()

    year_match = YEAR_PATTERN.search(text)
    if year_match:
        return int(year_match.group(0)), year_match.span()
    return None, None


def _normalize_author(author: str) -> str:
    author = normalize_text(author.replace("..", "."))
    author = author.rstrip(",")
    author = re.sub(r"\s*,\s*", ", ", author)
    author = re.sub(r"\s+", " ", author)
    return author


def _extract_authors(author_segment: str) -> list[str]:
    segment = author_segment.replace("…", "...").strip().rstrip(",")
    segment = segment.replace(" & ", ", ")
    matches = AUTHOR_PATTERN.findall(segment)
    if matches:
        return [_normalize_author(item) for item in matches]

    fallback: list[str] = []
    for chunk in segment.split(","):
        part = normalize_text(chunk)
        if not part:
            continue
        if len(part) > 1 and part[0].isupper():
            fallback.append(part)
    return fallback


def _extract_title(text: str, year_span: tuple[int, int] | None) -> str | None:
    if not year_span:
        return None

    tail = text[year_span[1] :].lstrip(").,;: ")
    if not tail:
        return None

    sentence_match = re.match(r"(.+?)\.\s+[A-Z]", tail)
    if sentence_match:
        title = sentence_match.group(1).strip()
        return title if len(title) >= 6 else None

    short_match = re.match(r"(.+?)\.", tail)
    if short_match:
        title = short_match.group(1).strip()
        return title if len(title) >= 6 else None

    return tail.strip() if len(tail.strip()) >= 6 else None


def parse_reference(raw_input: str) -> ParsedReference:
    text = normalize_text(raw_input)
    doi = extract_doi(text)
    year, year_span = _extract_year(text)

    authors: list[str] = []
    if year_span:
        author_segment = text[: year_span[0]]
        authors = _extract_authors(author_segment)

    title = _extract_title(text, year_span)

    return ParsedReference(
        raw_input=raw_input,
        title=title,
        authors=authors,
        year=year,
        doi=doi,
    )

