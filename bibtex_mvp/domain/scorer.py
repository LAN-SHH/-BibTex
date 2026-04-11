from __future__ import annotations

import re

from rapidfuzz import fuzz

from .models import CandidateRecord


def normalize_title(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_author(value: str) -> str:
    value = value.strip().lower()
    if "," in value:
        parts = [x.strip() for x in value.split(",", 1)]
        surname = re.sub(r"[^a-z]", "", parts[0])
        given = re.sub(r"[^a-z]", "", parts[1])
        initials = given[:2]
        return f"{surname},{initials}"
    tokens = [re.sub(r"[^a-z]", "", t) for t in value.split() if t]
    if not tokens:
        return ""
    surname = tokens[-1]
    initials = "".join(t[0] for t in tokens[:-1] if t)
    return f"{surname},{initials[:2]}"


def title_similarity(left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    score = fuzz.token_sort_ratio(normalize_title(left), normalize_title(right))
    return float(score) / 100.0


def year_similarity(left: int | None, right: int | None) -> float:
    if left is None or right is None:
        return 0.0
    if left == right:
        return 1.0
    if abs(left - right) == 1:
        return 0.5
    return 0.0


def author_similarity(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0

    left_norm = [normalize_author(v) for v in left]
    right_norm = [normalize_author(v) for v in right]
    if left_norm == right_norm:
        return 1.0

    left_set = set(left_norm)
    right_set = set(right_norm)
    intersection = len(left_set & right_set)
    union = len(left_set | right_set)
    if union == 0:
        return 0.0
    return intersection / union


def score_candidate(
    candidate: CandidateRecord,
    parsed_title: str | None,
    parsed_authors: list[str],
    parsed_year: int | None,
) -> CandidateRecord:
    t_score = title_similarity(parsed_title, candidate.title)
    y_score = year_similarity(parsed_year, candidate.year)
    a_score = author_similarity(parsed_authors, candidate.authors)

    weighted_sum = 0.0
    weight_total = 0.0

    if parsed_title and candidate.title:
        weighted_sum += 0.7 * t_score
        weight_total += 0.7
    if parsed_year is not None and candidate.year is not None:
        weighted_sum += 0.2 * y_score
        weight_total += 0.2
    if parsed_authors and candidate.authors:
        weighted_sum += 0.1 * a_score
        weight_total += 0.1

    final_score = (weighted_sum / weight_total) if weight_total > 0 else 0.0

    candidate.title_score = round(t_score, 4)
    candidate.year_score = round(y_score, 4)
    candidate.author_score = round(a_score, 4)
    candidate.score = round(final_score, 4)
    return candidate
