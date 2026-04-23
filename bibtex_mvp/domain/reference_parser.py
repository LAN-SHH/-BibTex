from __future__ import annotations

import re

from .input_classifier import extract_doi, normalize_text
from .models import ParsedReference

YEAR_BRACKET_PATTERN = re.compile(r"\((19|20)\d{2}[a-z]?\)")
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
AUTHOR_COMMA_INITIAL_PATTERN = re.compile(r"([A-Za-zÀ-ÖØ-öø-ÿ'`-]+,\s*(?:[A-Z]\.\s*)+)")
VANCOUVER_AUTHOR_PATTERN = re.compile(
    r"^[A-Za-zÀ-ÖØ-öø-ÿ'`-]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ'`-]+)*\s+(?:[A-Z]\.?){1,5}$"
)
CN_JOL_PATTERN = re.compile(
    r"^(?:\[\d+\]\s*)?(?P<authors>.+?)\.\s*(?P<title>.+?)\[(?:J|J/OL|J\\?/OL)\]\.\s*(?P<rest>.+)$",
    re.IGNORECASE,
)


def _extract_year(text: str) -> tuple[int | None, tuple[int, int] | None]:
    bracket_match = YEAR_BRACKET_PATTERN.search(text)
    if bracket_match:
        year = int(re.search(r"(19|20)\d{2}", bracket_match.group(0)).group(0))
        return year, bracket_match.span()

    year_matches = list(YEAR_PATTERN.finditer(text))
    if not year_matches:
        return None, None
    chosen = year_matches[-1]
    return int(chosen.group(0)), chosen.span()


def _normalize_author(author: str) -> str:
    author = normalize_text(author.replace("..", ".").replace("…", "..."))
    author = author.rstrip(",;")
    author = re.sub(r"\s*,\s*", ", ", author)
    author = re.sub(r"\s+", " ", author)
    return author


def _initials_with_dots(token: str) -> str:
    letters = re.findall(r"[A-Za-z]", token.upper())
    return "".join(f"{ch}." for ch in letters)


def _parse_vancouver_author(chunk: str) -> str | None:
    part = normalize_text(chunk).strip(",.;")
    if not part or re.search(r"\bet\s+al\b", part, re.IGNORECASE):
        return None
    if not VANCOUVER_AUTHOR_PATTERN.match(part):
        return None
    bits = part.split()
    if len(bits) < 2:
        return None
    surname = " ".join(bits[:-1]).strip()
    initials = _initials_with_dots(bits[-1])
    if not surname:
        return None
    if initials:
        return f"{surname}, {initials}"
    return surname


def _extract_authors(author_segment: str) -> list[str]:
    segment = author_segment.replace("…", "...").strip().rstrip(",")
    segment = segment.replace(" & ", ", ")

    comma_initial_matches = AUTHOR_COMMA_INITIAL_PATTERN.findall(segment)
    if comma_initial_matches:
        return [_normalize_author(item) for item in comma_initial_matches]

    vancouver_authors: list[str] = []
    for chunk in segment.split(","):
        parsed = _parse_vancouver_author(chunk)
        if parsed:
            vancouver_authors.append(_normalize_author(parsed))
    if vancouver_authors:
        return vancouver_authors

    fallback: list[str] = []
    for chunk in segment.split(","):
        part = normalize_text(chunk).strip(",.;")
        if not part:
            continue
        if len(part) > 1 and part[0].isupper():
            fallback.append(_normalize_author(part))
    return fallback


def _is_year_trailing(text: str, year_span: tuple[int, int]) -> bool:
    tail = text[year_span[1] :].strip(").,;: ")
    return not bool(re.search(r"[A-Za-z]", tail))


def _extract_title_from_post_year(text: str, year_span: tuple[int, int] | None) -> str | None:
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

    tail = tail.strip()
    return tail if len(tail) >= 6 else None


def _extract_title_and_authors_for_trailing_year(
    text: str,
    year_span: tuple[int, int],
) -> tuple[str | None, list[str]]:
    prefix = text[: year_span[0]].strip().rstrip(".;: ")
    if not prefix:
        return None, []
    segments = [seg.strip(" .;:") for seg in re.split(r"\.\s+", prefix) if seg.strip(" .;:")]
    if len(segments) < 2:
        return None, _extract_authors(prefix)
    author_segment = segments[0]
    title_segment = segments[1]
    title = title_segment if len(title_segment) >= 6 else None
    return title, _extract_authors(author_segment)


def _parse_cn_jol_reference(text: str) -> tuple[str | None, list[str], int | None] | None:
    match = CN_JOL_PATTERN.match(text)
    if not match:
        return None
    authors_raw = normalize_text(match.group("authors"))
    title_raw = normalize_text(match.group("title"))
    rest_raw = normalize_text(match.group("rest"))
    if not title_raw:
        return None

    authors: list[str] = []
    for chunk in authors_raw.replace("，", ",").split(","):
        part = normalize_text(chunk).strip(",.;")
        if not part or part in {"等", "et al", "et al."}:
            continue
        authors.append(part)

    year_match = YEAR_PATTERN.search(rest_raw)
    year = int(year_match.group(0)) if year_match else None
    return title_raw, authors, year


def parse_reference(raw_input: str) -> ParsedReference:
    text = normalize_text(raw_input)
    doi = extract_doi(text)

    cn_jol_parsed = _parse_cn_jol_reference(text)
    if cn_jol_parsed is not None:
        title, authors, year = cn_jol_parsed
        return ParsedReference(
            raw_input=raw_input,
            title=title,
            authors=authors,
            year=year,
            doi=doi,
        )

    year, year_span = _extract_year(text)

    authors: list[str] = []
    title: str | None = None

    if year_span and _is_year_trailing(text, year_span):
        title, authors = _extract_title_and_authors_for_trailing_year(text, year_span)
    else:
        if year_span:
            authors = _extract_authors(text[: year_span[0]])
        title = _extract_title_from_post_year(text, year_span)

    return ParsedReference(
        raw_input=raw_input,
        title=title,
        authors=authors,
        year=year,
        doi=doi,
    )
