from __future__ import annotations

import re

import bibtexparser

from .bibtex_key import build_bib_key
from .models import BibKeyRule, CandidateRecord


def _replace_bibtex_key(raw_bibtex: str, key: str) -> str:
    try:
        db = bibtexparser.loads(raw_bibtex)
        if db.entries:
            db.entries[0]["ID"] = key
            return bibtexparser.dumps(db)
    except Exception:
        pass

    return re.sub(r"(@\w+\{)([^,]+)", rf"\g<1>{key}", raw_bibtex, count=1)


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

