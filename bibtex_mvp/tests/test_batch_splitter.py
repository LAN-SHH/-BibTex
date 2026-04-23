from __future__ import annotations

from bibtex_mvp.domain.batch_splitter import is_too_short, split_batch_input
from bibtex_mvp.domain.models import SplitReasonCode


def test_is_too_short_for_plain_text() -> None:
    assert is_too_short("abc")
    assert not is_too_short("10.1016/j.neulet.2007.02.081")
    assert not is_too_short("Zhou Y. Functional dysconnectivity. 2007.")


def test_split_batch_ok_with_blank_lines() -> None:
    raw = (
        "Barch DM, Ceaser A. Cognition in schizophrenia. Trends in Cognitive Sciences. 2012.\n\n"
        "Buckner RL, Andrews-Hanna JR, Schacter DL. The brain's default network. 2008."
    )
    result = split_batch_input(raw)
    assert result.reason_code == SplitReasonCode.OK
    assert result.is_ambiguous is False
    assert len(result.items) == 2


def test_split_batch_ambiguous_single() -> None:
    raw = (
        "Barch DM, Ceaser A. Cognition in schizophrenia. 2012. "
        "Buckner RL, Andrews-Hanna JR, Schacter DL. The brain's default network. 2008."
    )
    result = split_batch_input(raw)
    assert result.is_ambiguous is True
    assert result.reason_code == SplitReasonCode.AMBIGUOUS_SINGLE
    assert result.ambiguous_indexes == [1]


def test_split_batch_too_short() -> None:
    result = split_batch_input("abc")
    assert result.is_ambiguous is True
    assert result.reason_code == SplitReasonCode.TOO_SHORT
    assert result.ambiguous_indexes == [1]

