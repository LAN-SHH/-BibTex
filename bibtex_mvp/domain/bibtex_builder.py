from __future__ import annotations

import re

import bibtexparser

from .bibtex_key import build_bib_key
from .models import BibKeyRule, CandidateRecord


def _sanitize_bibtex_for_parser(raw_bibtex: str) -> str:
    # Crossref occasionally returns bare month tokens like month=june.
    # Wrap bareword values so bibtexparser can parse and reformat consistently.
    return re.sub(
        r"=\s*([A-Za-z][A-Za-z0-9_-]*)\s*([,}])",
        lambda m: f"={{{m.group(1)}}}{m.group(2)}",
        raw_bibtex,
    )


def _try_parse_and_dump(raw_bibtex: str, key: str) -> str | None:
    try:
        db = bibtexparser.loads(raw_bibtex)
        if db.entries:
            db.entries[0]["ID"] = key
            return bibtexparser.dumps(db).strip()
    except Exception:
        return None
    return None


def _force_multiline_bibtex(raw_bibtex: str) -> str:
    text = re.sub(r"\s+", " ", raw_bibtex.strip())
    text = re.sub(r"(@\w+\{[^,]+,)\s*", r"\1\n  ", text)
    text = re.sub(r",\s*([A-Za-z][A-Za-z0-9_-]*\s*=)", r",\n  \1", text)
    text = re.sub(r"\s*}\s*$", "\n}", text)
    return text


def _replace_bibtex_key(raw_bibtex: str, key: str) -> str:
    parsed = _try_parse_and_dump(raw_bibtex, key)
    if parsed:
        return parsed

    sanitized = _sanitize_bibtex_for_parser(raw_bibtex)
    parsed_sanitized = _try_parse_and_dump(sanitized, key)
    if parsed_sanitized:
        return parsed_sanitized

    replaced_key = re.sub(r"(@\w+\{)([^,]+)", rf"\g<1>{key}", raw_bibtex, count=1)
    return _force_multiline_bibtex(replaced_key)


def _build_minimal_bibtex(candidate: CandidateRecord, key: str) -> str:
    authors = " and ".join(candidate.authors)
    entry_type = candidate.raw.get("entrytype", "article")
    fields: list[str] = []
    if candidate.title:
        fields.append(f"  title = {{{candidate.title}}}")
    if authors:
        fields.append(f"  author = {{{authors}}}")
    if candidate.year:
        fields.append(f"  year = {{{candidate.year}}}")
    if candidate.raw.get("journal"):
        fields.append(f"  journal = {{{candidate.raw['journal']}}}")
    if candidate.doi:
        fields.append(f"  doi = {{{candidate.doi}}}")

    return "@{entry}{{{key},\n{fields}\n}}".format(entry=entry_type, key=key, fields=",\n".join(fields))


def build_bibtex_for_candidate(
    candidate: CandidateRecord,
    rule: BibKeyRule,
    base_bibtex: str | None = None,
) -> tuple[str, str]:
    key = build_bib_key(rule, candidate.authors, candidate.year, candidate.title)
    if base_bibtex:
        return _replace_bibtex_key(base_bibtex, key), base_bibtex
    minimal = _build_minimal_bibtex(candidate, key)
    return minimal, minimal
