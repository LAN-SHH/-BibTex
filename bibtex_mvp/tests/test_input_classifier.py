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


def test_classify_reference_with_org_author() -> None:
    value = (
        "American Psychiatric Association. (1994). "
        "Diagnostic and statistical manual of mental disorders (4th ed.). Author."
    )
    assert classify_input(value) == InputKind.REFERENCE


def test_classify_vancouver_reference() -> None:
    value = (
        "Barch DM, Ceaser A. Cognition in schizophrenia: core psychological and neural mechanisms. "
        "Trends in Cognitive Sciences. 2012."
    )
    assert classify_input(value) == InputKind.REFERENCE
