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


def test_choose_auto_success_when_single_doi_candidate_has_reasonable_score() -> None:
    candidates = [
        _candidate("Close title", ["Li, X."], 2008, "", 0.88),
        _candidate("The Brain's Default Network", ["Buckner, R.L."], 2008, "10.1196/annals.1440.011", 0.73),
        _candidate("Noise title", ["Wang, H."], 2020, "", 0.91),
    ]
    picked = choose_auto_success(
        candidates,
        "The brain's default network: anatomy, function, and relevance to disease",
        ["Buckner, R.L.", "Andrews-Hanna, J.R.", "Schacter, D.L."],
        2008,
        auto_threshold=0.92,
    )
    assert picked is not None
    assert picked.doi == "10.1196/annals.1440.011"


def test_choose_auto_success_when_top_doi_has_clear_margin() -> None:
    candidates = [
        _candidate("Top title", ["Buckner, R.L."], 2008, "10.1196/annals.1440.011", 0.734),
        _candidate("Noise title one", ["Foo, A."], 2008, "10.1196/annals.1427.007", 0.5569),
        _candidate("Noise title two", ["Bar, B."], 2008, "10.1196/annals.1427.010", 0.5547),
    ]
    picked = choose_auto_success(
        candidates,
        "The brain's default network: anatomy, function, and relevance to disease",
        ["Buckner, R.L.", "Andrews-Hanna, J.R.", "Schacter, D.L."],
        2008,
        auto_threshold=0.92,
    )
    assert picked is not None
    assert picked.doi == "10.1196/annals.1440.011"
