from __future__ import annotations

from .models import CandidateRecord
from .scorer import normalize_author, normalize_title


def is_perfect_match(
    candidate: CandidateRecord,
    parsed_title: str | None,
    parsed_authors: list[str],
    parsed_year: int | None,
) -> bool:
    if not parsed_title or parsed_year is None or not parsed_authors:
        return False
    if candidate.year != parsed_year:
        return False
    if normalize_title(candidate.title) != normalize_title(parsed_title):
        return False
    left = [normalize_author(v) for v in parsed_authors]
    right = [normalize_author(v) for v in candidate.authors]
    return len(left) == len(right) and left == right


def choose_auto_success(
    candidates: list[CandidateRecord],
    parsed_title: str | None,
    parsed_authors: list[str],
    parsed_year: int | None,
    auto_threshold: float,
) -> CandidateRecord | None:
    perfect_matches = [
        candidate
        for candidate in candidates
        if is_perfect_match(candidate, parsed_title, parsed_authors, parsed_year)
        and candidate.doi
    ]
    if perfect_matches:
        return sorted(perfect_matches, key=lambda c: c.score, reverse=True)[0]

    high_conf = [candidate for candidate in candidates if candidate.score >= auto_threshold and candidate.doi]
    if len(high_conf) == 1:
        return high_conf[0]

    doi_candidates = [candidate for candidate in candidates if candidate.doi]
    if len(doi_candidates) == 1:
        only = doi_candidates[0]
        year_ok = parsed_year is None or only.year is None or abs((only.year or 0) - parsed_year) <= 1
        if year_ok and only.score >= 0.70:
            return only

    if doi_candidates:
        ranked = sorted(doi_candidates, key=lambda c: c.score, reverse=True)
        top = ranked[0]
        second_score = ranked[1].score if len(ranked) > 1 else 0.0
        year_ok = parsed_year is None or top.year is None or abs((top.year or 0) - parsed_year) <= 1
        if year_ok and top.score >= 0.70 and (top.score - second_score) >= 0.10:
            return top
    return None
