from bibtex_mvp.domain.bibtex_key import build_bib_key
from bibtex_mvp.domain.models import BibKeyRule


def test_key_rule_author_year() -> None:
    key = build_bib_key(BibKeyRule.AUTHOR_YEAR, ["Zhou, Y."], 2007, "Functional dysconnectivity")
    assert key == "Zhou2007"


def test_key_rule_author_year_title() -> None:
    key = build_bib_key(BibKeyRule.AUTHOR_YEAR_TITLE, ["Zhou, Y."], 2007, "Functional dysconnectivity")
    assert key == "Zhou2007Functional"


def test_key_rule_title_year() -> None:
    key = build_bib_key(BibKeyRule.TITLE_YEAR, ["Zhou, Y."], 2007, "Functional dysconnectivity")
    assert key == "Functional2007"
