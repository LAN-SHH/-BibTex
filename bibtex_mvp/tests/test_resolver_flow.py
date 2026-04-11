import pytest

from bibtex_mvp.application.orchestrator import ResolverConfig
from bibtex_mvp.application.resolver import SingleEntryResolver
from bibtex_mvp.domain.models import BibKeyRule, CandidateRecord, ResultStatus


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
