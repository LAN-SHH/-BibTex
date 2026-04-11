from __future__ import annotations

import re
from urllib.parse import urlparse

from bibtex_mvp.domain.models import CandidateRecord


def _format_author(family: str, given: str) -> str:
    initials = "".join([part[0].upper() + "." for part in given.split() if part])
    if not family:
        return given.strip()
    if not initials:
        return family.strip()
    return f"{family.strip()}, {initials}"


def _name_to_family_initials(display_name: str) -> str:
    parts = [p for p in display_name.split() if p]
    if not parts:
        return ""
    family = parts[-1]
    given = " ".join(parts[:-1])
    return _format_author(family, given)


def _parse_year_from_crossref(item: dict) -> int | None:
    for key in ("issued", "published-print", "published-online", "created"):
        info = item.get(key) or {}
        date_parts = info.get("date-parts") or []
        if date_parts and date_parts[0]:
            try:
                return int(date_parts[0][0])
            except (TypeError, ValueError):
                continue
    return None


def _normalize_doi(raw_doi: str | None) -> str | None:
    if not raw_doi:
        return None
    doi = raw_doi.strip()
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    doi = doi.replace("https://dx.doi.org/", "").replace("http://dx.doi.org/", "")
    return doi.lower()


def map_crossref_item(item: dict) -> CandidateRecord:
    title_list = item.get("title") or []
    title = title_list[0].strip() if title_list else ""
    authors_raw = item.get("author") or []
    authors = [_format_author(a.get("family", ""), a.get("given", "")) for a in authors_raw]
    doi = _normalize_doi(item.get("DOI"))
    journal_list = item.get("container-title") or []
    journal = journal_list[0].strip() if journal_list else ""
    entry_type = item.get("type", "article")
    return CandidateRecord(
        title=title,
        authors=[a for a in authors if a],
        year=_parse_year_from_crossref(item),
        doi=doi,
        source="crossref",
        raw={"journal": journal, "entrytype": entry_type},
    )


def map_openalex_item(item: dict) -> CandidateRecord:
    title = (item.get("display_name") or "").strip()
    year = item.get("publication_year")
    doi = _normalize_doi(item.get("doi"))
    if doi and doi.startswith("https://"):
        path = urlparse(doi).path.strip("/")
        if path.startswith("10."):
            doi = path.lower()

    authorships = item.get("authorships") or []
    authors: list[str] = []
    for author in authorships:
        display_name = ((author.get("author") or {}).get("display_name") or "").strip()
        if display_name:
            authors.append(_name_to_family_initials(display_name))

    source_info = (item.get("primary_location") or {}).get("source") or {}
    journal = source_info.get("display_name") or ""
    entry_type = "article"
    if item.get("type"):
        entry_type = re.sub(r"\s+", "", item["type"].lower())

    return CandidateRecord(
        title=title,
        authors=[a for a in authors if a],
        year=year if isinstance(year, int) else None,
        doi=doi,
        source="openalex",
        raw={"journal": journal, "entrytype": entry_type},
    )

