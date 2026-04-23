from bibtex_mvp.domain.reference_parser import parse_reference


def test_parse_reference_extracts_core_fields() -> None:
    raw = (
        "Zhou, Y., Liang, M., Jiang, T., Tian, L., Liu, Y., Liu, Z., ... & Kuang, H. (2007). "
        "Functional dysconnectivity of the dorsolateral prefrontal cortex in first-episode schizophrenia "
        "using resting-state fMRI. Neuroscience Letters, 417(3), 297-302. "
        "https://doi.org/10.1016/j.neulet.2007.02.081"
    )
    parsed = parse_reference(raw)
    assert parsed.doi == "10.1016/j.neulet.2007.02.081"
    assert parsed.year == 2007
    assert parsed.title is not None
    assert "Functional dysconnectivity" in parsed.title
    assert parsed.authors
    assert parsed.authors[0].startswith("Zhou,")


def test_parse_reference_vancouver_style_with_trailing_year() -> None:
    raw = (
        "Buckner RL, Andrews-Hanna JR, Schacter DL. "
        "The brain's default network: anatomy, function, and relevance to disease. "
        "Annals of the New York Academy of Sciences. 2008."
    )
    parsed = parse_reference(raw)
    assert parsed.year == 2008
    assert parsed.title == "The brain's default network: anatomy, function, and relevance to disease"
    assert parsed.authors[:3] == ["Buckner, R.L.", "Andrews-Hanna, J.R.", "Schacter, D.L."]


def test_parse_reference_cn_jol_style() -> None:
    raw = (
        "[2] POWER J D, COHEN A L, NELSON S M, 等. "
        "Functional Network Organization of the Human Brain[J/OL]. "
        "NEURON, 2011, 72(4): 665-678. DOI:10.1016/j.neuron.2011.09.006."
    )
    parsed = parse_reference(raw)
    assert parsed.title == "Functional Network Organization of the Human Brain"
    assert parsed.year == 2011
    assert parsed.doi == "10.1016/j.neuron.2011.09.006"
    assert parsed.authors[:3] == ["POWER J D", "COHEN A L", "NELSON S M"]
