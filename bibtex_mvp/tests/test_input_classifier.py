from bibtex_mvp.domain.input_classifier import classify_input
from bibtex_mvp.domain.models import InputKind


def test_classify_doi_input() -> None:
    value = "https://doi.org/10.1016/j.neulet.2007.02.081"
    assert classify_input(value) == InputKind.DOI


def test_classify_reference_input() -> None:
    value = (
        "Zhou, Y., Liang, M., Jiang, T., Tian, L., Liu, Y., & Kuang, H. (2007). "
        "Functional dysconnectivity of the dorsolateral prefrontal cortex in first-episode schizophrenia "
        "using resting-state fMRI. Neuroscience Letters, 417(3), 297-302."
    )
    assert classify_input(value) == InputKind.REFERENCE


def test_classify_title_input() -> None:
    value = "Functional dysconnectivity of the dorsolateral prefrontal cortex in first-episode schizophrenia"
    assert classify_input(value) == InputKind.TITLE

