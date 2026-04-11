from bibtex_mvp.domain.matcher import choose_auto_success, is_perfect_match
from bibtex_mvp.domain.models import CandidateRecord


def _candidate(
    title: str,
    authors: list[str],
    year: int,
    doi: str,
    score: float,
) -> CandidateRecord:
    return CandidateRecord(
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        source="crossref",
        score=score,
    )


def test_is_perfect_match_true() -> None:
    candidate = _candidate(
        title="Functional dysconnectivity of the dorsolateral prefrontal cortex in first-episode schizophrenia",
        authors=["Zhou, Y.", "Liang, M."],
        year=2007,
        doi="10.1016/j.neulet.2007.02.081",
        score=0.99,
    )
    assert is_perfect_match(
        candidate,
        "Functional dysconnectivity of the dorsolateral prefrontal cortex in first-episode schizophrenia",
        ["Zhou, Y.", "Liang, M."],
        2007,
    )


def test_choose_auto_success_prefers_perfect_even_with_multiple_candidates() -> None:
    candidates = [
        _candidate(
            title="Another title",
            authors=["Wang, H."],
            year=2007,
            doi="10.1000/other",
            score=0.95,
        ),
        _candidate(
            title="Functional dysconnectivity of the dorsolateral prefrontal cortex in first-episode schizophrenia",
            authors=["Zhou, Y.", "Liang, M."],
            year=2007,
            doi="10.1016/j.neulet.2007.02.081",
            score=0.90,
        ),
    ]
    picked = choose_auto_success(
        candidates,
        "Functional dysconnectivity of the dorsolateral prefrontal cortex in first-episode schizophrenia",
        ["Zhou, Y.", "Liang, M."],
        2007,
        auto_threshold=0.92,
    )
    assert picked is not None
    assert picked.doi == "10.1016/j.neulet.2007.02.081"


def test_choose_auto_success_when_only_one_high_confidence() -> None:
    candidates = [
        _candidate("A", ["Li, X."], 2020, "10.1000/a", 0.93),
        _candidate("B", ["Li, X."], 2020, "10.1000/b", 0.70),
    ]
    picked = choose_auto_success(candidates, "No Match", [], None, auto_threshold=0.92)
    assert picked is not None
    assert picked.doi == "10.1000/a"

