from __future__ import annotations

import re

from .models import BibKeyRule


def _slug_token(text: str, fallback: str) -> str:
    token = re.sub(r"[^a-z0-9]", "", text.lower())
    return token or fallback


def _first_author_surname(authors: list[str]) -> str:
    if not authors:
        return "unknown"
    first = authors[0]
    if "," in first:
        return _slug_token(first.split(",", 1)[0], "unknown")
    return _slug_token(first.split()[-1], "unknown")


def _first_title_word(title: str) -> str:
    if not title:
        return "untitled"
    parts = re.split(r"\s+", title.strip())
    return _slug_token(parts[0], "untitled")


def build_bib_key(rule: BibKeyRule, authors: list[str], year: int | None, title: str) -> str:
    author = _first_author_surname(authors)
    y = str(year) if year is not None else "noyear"
    title_word = _first_title_word(title)

    if rule == BibKeyRule.AUTHOR_YEAR:
        return f"{author}{y}"
    if rule == BibKeyRule.AUTHOR_YEAR_TITLE:
        return f"{author}{y}{title_word}"
    return f"{title_word}{y}"

