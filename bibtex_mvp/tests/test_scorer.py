from bibtex_mvp.domain.models import CandidateRecord
from bibtex_mvp.domain.scorer import score_candidate


def test_title_only_score_can_reach_high_confidence() -> None:
    candidate = CandidateRecord(
        title="Functional dysconnectivity of the dorsolateral prefrontal cortex",
        authors=["Zhou, Y."],
        year=2007,
        doi="10.1016/j.neulet.2007.02.081",
        source="crossref",
    )
    scored = score_candidate(
        candidate,
        parsed_title="Functional dysconnectivity of the dorsolateral prefrontal cortex",
        parsed_authors=[],
        parsed_year=None,
    )
    assert scored.score >= 0.95


def test_reference_style_match_score_is_not_zero() -> None:
    candidate = CandidateRecord(
        title="Distinct brain networks for adaptive and stable task control in humans",
        authors=["Dosenbach, N.U.F.", "Fair, D.A.", "Miezin, F.M."],
        year=2007,
        doi="10.1073/pnas.0704320104",
        source="crossref",
    )
    scored = score_candidate(
        candidate,
        parsed_title="Distinct brain networks for adaptive and stable task control in humans",
        parsed_authors=["Dosenbach, N.U.F.", "Fair, D.A.", "Miezin, F.M."],
        parsed_year=2007,
    )
    assert scored.score > 0.9
