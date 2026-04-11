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

