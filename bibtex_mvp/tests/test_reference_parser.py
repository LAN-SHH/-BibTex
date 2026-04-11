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

