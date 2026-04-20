from bibtex_mvp.domain.bibtex_builder import build_bibtex_for_candidate
from bibtex_mvp.domain.models import BibKeyRule, CandidateRecord


def test_build_bibtex_reformats_single_line_entry_with_bare_month() -> None:
    candidate = CandidateRecord(
        title="Distinct brain networks for adaptive and stable task control in humans",
        authors=["Dosenbach, N.U.F.", "Fair, D.A.", "Miezin, F.M."],
        year=2007,
        doi="10.1073/pnas.0704320104",
        source="crossref",
    )
    one_line = (
        "@article{Dosenbach_2007, title={Distinct brain networks for adaptive and stable task control in humans}, "
        "volume={104}, DOI={10.1073/pnas.0704320104}, year={2007}, month=june }"
    )
    bibtex, _ = build_bibtex_for_candidate(
        candidate,
        BibKeyRule.AUTHOR_YEAR,
        base_bibtex=one_line,
    )
    assert "@article{Dosenbach2007" in bibtex
    assert "\n" in bibtex
    assert "month = {june}" in bibtex

