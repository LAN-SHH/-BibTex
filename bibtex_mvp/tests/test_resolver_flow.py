import asyncio

import pytest

from bibtex_mvp.application.orchestrator import BatchCancelToken, ResolverConfig
from bibtex_mvp.application.resolver import SingleEntryResolver
from bibtex_mvp.domain.models import BatchProgressEvent, BatchProgressStage, BibKeyRule, CandidateRecord, ResultStatus


class FakeCrossrefClient:
    def __init__(self, title_items: list[dict], biblio_items: list[dict] | None = None) -> None:
        self.title_items = title_items
        self.biblio_items = biblio_items or []

    async def search_by_title(self, title: str, rows: int = 20) -> list[dict]:
        return self.title_items

    async def search_by_bibliographic(self, reference_text: str, rows: int = 20) -> list[dict]:
        return self.biblio_items

    async def fetch_work_by_doi(self, doi: str) -> dict | None:
        return None

    async def fetch_bibtex(self, doi: str) -> str | None:
        return "@article{origin, title={X}, year={2007}, doi={10.1/test}}"


class FakeOpenAlexClient:
    async def search_works(self, query: str, per_page: int = 20) -> list[dict]:
        return []

    async def fetch_work_by_doi(self, doi: str) -> dict | None:
        return None


class FakeDoiService:
    def __init__(self, candidate_by_doi: dict[str, CandidateRecord] | None = None) -> None:
        self.candidate_by_doi = candidate_by_doi or {}

    async def fetch_candidate_by_doi(self, doi: str) -> CandidateRecord | None:
        return self.candidate_by_doi.get(doi)

    async def fetch_bibtex_by_doi(self, doi: str) -> str | None:
        return "@article{origin, title={X}, year={2007}, doi={%s}}" % doi


def _crossref_item(title: str, authors: list[tuple[str, str]], year: int, doi: str) -> dict:
    return {
        "title": [title],
        "author": [{"family": f, "given": g} for f, g in authors],
        "issued": {"date-parts": [[year]]},
        "DOI": doi,
        "type": "journal-article",
        "container-title": ["Test Journal"],
    }


@pytest.mark.asyncio
async def test_resolver_success_with_perfect_match_among_multiple() -> None:
    perfect = _crossref_item(
        "Functional dysconnectivity of the dorsolateral prefrontal cortex in first-episode schizophrenia",
        [("Zhou", "Y."), ("Liang", "M.")],
        2007,
        "10.1016/j.neulet.2007.02.081",
    )
    distractor = _crossref_item("Another study title", [("Wang", "H.")], 2007, "10.1000/other")

    resolver = SingleEntryResolver(
        crossref_client=FakeCrossrefClient([distractor, perfect]),
        openalex_client=FakeOpenAlexClient(),
        doi_service=FakeDoiService(),
    )

    raw = (
        "Zhou, Y., Liang, M. (2007). Functional dysconnectivity of the dorsolateral prefrontal cortex "
        "in first-episode schizophrenia. Neuroscience Letters."
    )
    result = await resolver.resolve(raw, BibKeyRule.AUTHOR_YEAR, ResolverConfig())
    assert result.status == ResultStatus.SUCCESS
    assert result.selected is not None
    assert result.selected.doi == "10.1016/j.neulet.2007.02.081"
    assert result.bibtex and "@article{" in result.bibtex


@pytest.mark.asyncio
async def test_resolver_pending_when_multiple_and_no_auto_success() -> None:
    resolver = SingleEntryResolver(
        crossref_client=FakeCrossrefClient(
            [
                _crossref_item("Title A", [("Li", "X.")], 2020, "10.1000/a"),
                _crossref_item("Title B", [("Li", "X.")], 2021, "10.1000/b"),
            ]
        ),
        openalex_client=FakeOpenAlexClient(),
        doi_service=FakeDoiService(),
    )
    result = await resolver.resolve(
        "A Generic Topic",
        BibKeyRule.AUTHOR_YEAR,
        ResolverConfig(candidate_floor_threshold=0.0),
    )
    assert result.status == ResultStatus.PENDING
    assert len(result.candidates) >= 1
    assert result.scholar_url is not None


@pytest.mark.asyncio
async def test_resolver_failed_when_no_candidates() -> None:
    resolver = SingleEntryResolver(
        crossref_client=FakeCrossrefClient([]),
        openalex_client=FakeOpenAlexClient(),
        doi_service=FakeDoiService(),
    )
    result = await resolver.resolve("Unknown title", BibKeyRule.AUTHOR_YEAR, ResolverConfig())
    assert result.status == ResultStatus.FAILED
    assert result.scholar_url is not None


@pytest.mark.asyncio
async def test_resolver_reference_pending_when_no_candidates() -> None:
    resolver = SingleEntryResolver(
        crossref_client=FakeCrossrefClient([]),
        openalex_client=FakeOpenAlexClient(),
        doi_service=FakeDoiService(),
    )
    raw = (
        "Barch DM, Ceaser A. Cognition in schizophrenia: core psychological and neural mechanisms. "
        "Trends in Cognitive Sciences. 2012."
    )
    result = await resolver.resolve(raw, BibKeyRule.AUTHOR_YEAR, ResolverConfig())
    assert result.status == ResultStatus.PENDING
    assert len(result.candidates) == 1
    assert result.candidates[0].source == "parsed"


@pytest.mark.asyncio
async def test_resolver_reference_fallback_pending_without_doi() -> None:
    resolver = SingleEntryResolver(
        crossref_client=FakeCrossrefClient(
            [_crossref_item("Unrelated title", [("Someone", "A.")], 2019, "10.1000/unrelated")]
        ),
        openalex_client=FakeOpenAlexClient(),
        doi_service=FakeDoiService(),
    )
    raw = (
        "American Psychiatric Association. (1994). "
        "Diagnostic and statistical manual of mental disorders (4th ed.). Author."
    )
    result = await resolver.resolve(raw, BibKeyRule.AUTHOR_YEAR, ResolverConfig())
    assert result.status == ResultStatus.PENDING
    assert len(result.candidates) == 1
    assert result.candidates[0].source == "parsed"
    assert result.candidates[0].doi is None


@pytest.mark.asyncio
async def test_resolver_success_for_title_only_with_single_exact_candidate() -> None:
    resolver = SingleEntryResolver(
        crossref_client=FakeCrossrefClient(
            [
                _crossref_item(
                    "Functional dysconnectivity of the dorsolateral prefrontal cortex",
                    [("Zhou", "Y.")],
                    2007,
                    "10.1016/j.neulet.2007.02.081",
                )
            ]
        ),
        openalex_client=FakeOpenAlexClient(),
        doi_service=FakeDoiService(),
    )

    result = await resolver.resolve(
        "Functional dysconnectivity of the dorsolateral prefrontal cortex",
        BibKeyRule.AUTHOR_YEAR,
        ResolverConfig(),
    )
    assert result.status == ResultStatus.SUCCESS
    assert result.selected is not None
    assert result.selected.doi == "10.1016/j.neulet.2007.02.081"


@pytest.mark.asyncio
async def test_resolve_batch_keeps_order_and_continues_after_failure() -> None:
    class BranchCrossrefClient(FakeCrossrefClient):
        async def search_by_title(self, title: str, rows: int = 20) -> list[dict]:
            if "missing" in title.lower():
                return []
            return [_crossref_item(title, [("Li", "X.")], 2020, f"10.1000/{title.lower().replace(' ', '')}")]

        async def search_by_bibliographic(self, reference_text: str, rows: int = 20) -> list[dict]:
            return []

    resolver = SingleEntryResolver(
        crossref_client=BranchCrossrefClient([]),
        openalex_client=FakeOpenAlexClient(),
        doi_service=FakeDoiService(),
    )
    events: list[BatchProgressEvent] = []

    results = await resolver.resolve_batch(
        raw_inputs=["Good First", "Missing One", "Good Third"],
        key_rule=BibKeyRule.AUTHOR_YEAR,
        config=ResolverConfig(),
        progress_cb=lambda event: events.append(event),
    )

    assert [r.status for r in results] == [ResultStatus.SUCCESS, ResultStatus.FAILED, ResultStatus.SUCCESS]
    assert [r.raw_input for r in results] == ["Good First", "Missing One", "Good Third"]
    assert any(event.stage == BatchProgressStage.ITEM_FAILED and event.index == 2 for event in events)
    assert any(event.stage == BatchProgressStage.ITEM_DONE and event.index == 1 for event in events)
    assert any(event.stage == BatchProgressStage.ITEM_DONE and event.index == 3 for event in events)


@pytest.mark.asyncio
async def test_resolve_batch_cancel_marks_cancelled() -> None:
    class SlowCrossrefClient(FakeCrossrefClient):
        async def search_by_title(self, title: str, rows: int = 20) -> list[dict]:
            await asyncio.sleep(0.5)
            return [_crossref_item(title, [("Li", "X.")], 2020, f"10.1000/{title.lower().replace(' ', '')}")]

        async def search_by_bibliographic(self, reference_text: str, rows: int = 20) -> list[dict]:
            await asyncio.sleep(0.5)
            return []

    resolver = SingleEntryResolver(
        crossref_client=SlowCrossrefClient([]),
        openalex_client=FakeOpenAlexClient(),
        doi_service=FakeDoiService(),
    )
    token = BatchCancelToken()
    events: list[BatchProgressEvent] = []

    task = asyncio.create_task(
        resolver.resolve_batch(
            raw_inputs=["A", "B", "C"],
            key_rule=BibKeyRule.AUTHOR_YEAR,
            config=ResolverConfig(batch_concurrency=2),
            progress_cb=lambda event: events.append(event),
            cancel_token=token,
        )
    )
    await asyncio.sleep(0.1)
    token.cancel()
    results = await task

    assert len(results) == 3
    assert any(r.status == ResultStatus.CANCELLED for r in results)
    assert any(event.stage == BatchProgressStage.ITEM_CANCELLED for event in events)


def test_rebuild_result_bibtex_without_selected_still_updates_key() -> None:
    resolver = SingleEntryResolver(
        crossref_client=FakeCrossrefClient([]),
        openalex_client=FakeOpenAlexClient(),
        doi_service=FakeDoiService(),
    )
    from bibtex_mvp.domain.models import InputKind, ResolutionResult

    base = (
        "@article{OldKey, title={Dynamic reconfiguration of human brain networks during learning}, "
        "author={Bassett, D.S. and Wymbs, N.F.}, year={2011}, doi={10.1073/pnas.1018985108}}"
    )
    result = ResolutionResult(
        raw_input="x",
        input_kind=InputKind.DOI,
        status=ResultStatus.SUCCESS,
        selected=None,
        parsed_title=None,
        parsed_authors=[],
        parsed_year=None,
        doi="10.1073/pnas.1018985108",
        bibtex=base,
        bibtex_base=base,
    )

    updated = resolver.rebuild_result_bibtex(result, BibKeyRule.TITLE_YEAR)
    assert updated.bibtex is not None
    assert "@article{Dynamic2011" in updated.bibtex


def test_rebuild_result_bibtex_prefers_bibtex_over_selected() -> None:
    resolver = SingleEntryResolver(
        crossref_client=FakeCrossrefClient([]),
        openalex_client=FakeOpenAlexClient(),
        doi_service=FakeDoiService(),
    )
    from bibtex_mvp.domain.models import InputKind, ResolutionResult

    base = (
        "@article{OldKey, title={Dynamic reconfiguration of human brain networks during learning}, "
        "author={Bassett, D.S. and Wymbs, N.F.}, year={2011}, doi={10.1073/pnas.1018985108}}"
    )
    wrong_selected = CandidateRecord(
        title="Completely Wrong Title",
        authors=["Wrong, A."],
        year=1999,
        doi="10.0000/wrong",
        source="crossref",
    )
    result = ResolutionResult(
        raw_input="x",
        input_kind=InputKind.DOI,
        status=ResultStatus.SUCCESS,
        selected=wrong_selected,
        parsed_title="Wrong Parsed Title",
        parsed_authors=["Wrong, P."],
        parsed_year=2001,
        doi="10.0000/wrong",
        bibtex=base,
        bibtex_base=base,
    )

    updated = resolver.rebuild_result_bibtex(result, BibKeyRule.TITLE_YEAR)
    assert updated.bibtex is not None
    assert "@article{Dynamic2011" in updated.bibtex
