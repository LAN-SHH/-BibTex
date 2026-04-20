from __future__ import annotations

import asyncio

from bibtex_mvp.domain.bibtex_builder import build_bibtex_for_candidate
from bibtex_mvp.domain.input_classifier import classify_input, extract_doi, normalize_text
from bibtex_mvp.domain.matcher import choose_auto_success
from bibtex_mvp.domain.models import (
    BibKeyRule,
    CandidateRecord,
    InputKind,
    ParsedReference,
    ResolutionResult,
    ResultStatus,
)
from bibtex_mvp.domain.reference_parser import parse_reference
from bibtex_mvp.domain.scorer import normalize_title, score_candidate
from bibtex_mvp.infra.crossref_client import CrossrefClient
from bibtex_mvp.infra.doi_client import DoiService
from bibtex_mvp.infra.mapper import map_crossref_item, map_openalex_item
from bibtex_mvp.infra.openalex_client import OpenAlexClient
from bibtex_mvp.infra.scholar_url import build_scholar_search_url

from .orchestrator import ResolverConfig


class SingleEntryResolver:
    def __init__(
        self,
        crossref_client: CrossrefClient | None = None,
        openalex_client: OpenAlexClient | None = None,
        doi_service: DoiService | None = None,
    ) -> None:
        self.crossref_client = crossref_client or CrossrefClient()
        self.openalex_client = openalex_client or OpenAlexClient()
        self.doi_service = doi_service or DoiService(self.crossref_client, self.openalex_client)

    async def resolve(
        self,
        raw_input: str,
        key_rule: BibKeyRule,
        config: ResolverConfig | None = None,
    ) -> ResolutionResult:
        cfg = config or ResolverConfig()
        cleaned = normalize_text(raw_input)
        kind = classify_input(cleaned)

        if kind == InputKind.DOI:
            doi = extract_doi(cleaned)
            if not doi:
                return self._build_failed(raw_input, kind, "DOI 识别失败")
            return await self._resolve_doi_flow(
                raw_input=raw_input,
                input_kind=kind,
                doi=doi,
                key_rule=key_rule,
                parsed=ParsedReference(raw_input=raw_input, doi=doi),
            )

        if kind == InputKind.REFERENCE:
            parsed = parse_reference(cleaned)
            parsed.raw_input = raw_input
            if parsed.doi:
                return await self._resolve_doi_flow(
                    raw_input=raw_input,
                    input_kind=kind,
                    doi=parsed.doi,
                    key_rule=key_rule,
                    parsed=parsed,
                )
            parsed_title = parsed.title or cleaned
        else:
            parsed = ParsedReference(raw_input=raw_input, title=cleaned)
            parsed_title = cleaned

        candidates = await self._search_candidates(
            raw_input=raw_input,
            input_kind=kind,
            query_text=parsed_title,
            rows=cfg.max_rows,
        )
        if not candidates:
            if kind == InputKind.REFERENCE and parsed_title and (parsed.authors or parsed.year):
                fallback_candidate = CandidateRecord(
                    title=parsed_title,
                    authors=parsed.authors,
                    year=parsed.year,
                    doi=None,
                    source="parsed",
                    raw={"entrytype": "misc"},
                )
                return ResolutionResult(
                    raw_input=raw_input,
                    input_kind=kind,
                    status=ResultStatus.PENDING,
                    parsed_title=parsed_title,
                    parsed_authors=parsed.authors,
                    parsed_year=parsed.year,
                    candidates=[fallback_candidate],
                    scholar_url=build_scholar_search_url(parsed_title),
                    message="自动检索失败，可确认解析结果（无 DOI）",
                )
            return self._build_failed(
                raw_input=raw_input,
                input_kind=kind,
                message="自动检索失败",
                parsed=parsed,
                scholar_query=parsed_title,
            )

        scored = [score_candidate(c, parsed_title, parsed.authors, parsed.year) for c in candidates]
        scored.sort(key=lambda c: c.score, reverse=True)

        auto_choice = choose_auto_success(
            candidates=scored,
            parsed_title=parsed_title,
            parsed_authors=parsed.authors,
            parsed_year=parsed.year,
            auto_threshold=cfg.auto_accept_threshold,
        )
        if auto_choice:
            return await self._success_from_candidate(raw_input, kind, parsed, auto_choice, key_rule)

        visible_candidates = [c for c in scored if c.score >= cfg.candidate_floor_threshold]

        # For structured references, keep the best DOI candidate when score is lower than the normal floor.
        if not visible_candidates and kind == InputKind.REFERENCE:
            doi_candidates = [c for c in scored if c.doi]
            if doi_candidates and doi_candidates[0].score >= 0.55:
                visible_candidates = [doi_candidates[0]]

        if visible_candidates:
            return ResolutionResult(
                raw_input=raw_input,
                input_kind=kind,
                status=ResultStatus.PENDING,
                parsed_title=parsed_title,
                parsed_authors=parsed.authors,
                parsed_year=parsed.year,
                candidates=visible_candidates,
                scholar_url=build_scholar_search_url(parsed_title),
                message="命中候选结果，请确认后生成 BibTeX",
            )

        if kind == InputKind.REFERENCE and parsed_title and (parsed.authors or parsed.year):
            fallback_candidate = CandidateRecord(
                title=parsed_title,
                authors=parsed.authors,
                year=parsed.year,
                doi=None,
                source="parsed",
                raw={"entrytype": "misc"},
            )
            return ResolutionResult(
                raw_input=raw_input,
                input_kind=kind,
                status=ResultStatus.PENDING,
                parsed_title=parsed_title,
                parsed_authors=parsed.authors,
                parsed_year=parsed.year,
                candidates=[fallback_candidate],
                scholar_url=build_scholar_search_url(parsed_title),
                message="未检索到高置信 DOI，可确认解析结果（无 DOI）",
            )

        return self._build_failed(
            raw_input=raw_input,
            input_kind=kind,
            message="未找到可信候选",
            parsed=parsed,
            scholar_query=parsed_title,
        )

    async def finalize_candidate(
        self,
        pending_result: ResolutionResult,
        candidate: CandidateRecord,
        key_rule: BibKeyRule,
    ) -> ResolutionResult:
        parsed = ParsedReference(
            raw_input=pending_result.raw_input,
            title=pending_result.parsed_title,
            authors=pending_result.parsed_authors,
            year=pending_result.parsed_year,
            doi=candidate.doi,
        )
        return await self._success_from_candidate(
            raw_input=pending_result.raw_input,
            input_kind=pending_result.input_kind,
            parsed=parsed,
            candidate=candidate,
            key_rule=key_rule,
        )

    def rebuild_result_bibtex(self, result: ResolutionResult, key_rule: BibKeyRule) -> ResolutionResult:
        if not result.selected:
            return result
        bibtex, base_bibtex = build_bibtex_for_candidate(result.selected, key_rule, result.bibtex_base)
        result.bibtex = bibtex
        result.bibtex_base = base_bibtex
        return result

    async def _resolve_doi_flow(
        self,
        raw_input: str,
        input_kind: InputKind,
        doi: str,
        key_rule: BibKeyRule,
        parsed: ParsedReference,
    ) -> ResolutionResult:
        candidate = await self.doi_service.fetch_candidate_by_doi(doi)
        if not candidate:
            return self._build_failed(
                raw_input=raw_input,
                input_kind=input_kind,
                message="DOI 检索失败",
                parsed=parsed,
                scholar_query=parsed.title or doi,
            )
        return await self._success_from_candidate(raw_input, input_kind, parsed, candidate, key_rule)

    async def _success_from_candidate(
        self,
        raw_input: str,
        input_kind: InputKind,
        parsed: ParsedReference,
        candidate: CandidateRecord,
        key_rule: BibKeyRule,
    ) -> ResolutionResult:
        base_bibtex = None
        if candidate.doi:
            base_bibtex = await self.doi_service.fetch_bibtex_by_doi(candidate.doi)
        bibtex, stored_base = build_bibtex_for_candidate(candidate, key_rule, base_bibtex)

        return ResolutionResult(
            raw_input=raw_input,
            input_kind=input_kind,
            status=ResultStatus.SUCCESS,
            parsed_title=parsed.title,
            parsed_authors=parsed.authors,
            parsed_year=parsed.year,
            selected=candidate,
            doi=candidate.doi,
            bibtex=bibtex,
            bibtex_base=stored_base,
            message="BibTeX 生成成功",
        )

    async def _search_candidates(
        self,
        raw_input: str,
        input_kind: InputKind,
        query_text: str,
        rows: int,
    ) -> list[CandidateRecord]:
        bibliographic_query = raw_input if input_kind == InputKind.REFERENCE else query_text
        tasks = [
            self.crossref_client.search_by_title(query_text, rows=rows),
            self.openalex_client.search_works(query_text, per_page=rows),
            self.crossref_client.search_by_bibliographic(bibliographic_query, rows=rows),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        crossref_title_items = results[0] if isinstance(results[0], list) else []
        openalex_items = results[1] if isinstance(results[1], list) else []
        crossref_biblio_items = results[2] if isinstance(results[2], list) else []

        merged: list[CandidateRecord] = []
        for item in crossref_title_items:
            merged.append(map_crossref_item(item))
        for item in crossref_biblio_items:
            merged.append(map_crossref_item(item))
        for item in openalex_items:
            merged.append(map_openalex_item(item))

        return self._deduplicate([c for c in merged if c.title])

    def _deduplicate(self, candidates: list[CandidateRecord]) -> list[CandidateRecord]:
        by_key: dict[str, CandidateRecord] = {}
        for candidate in candidates:
            key = candidate.doi or f"{normalize_title(candidate.title)}|{candidate.year or 'noyear'}"
            if key not in by_key:
                by_key[key] = candidate
                continue
            existing = by_key[key]
            if existing.source == "openalex" and candidate.source == "crossref":
                by_key[key] = candidate
        return list(by_key.values())

    def _build_failed(
        self,
        raw_input: str,
        input_kind: InputKind,
        message: str,
        parsed: ParsedReference | None = None,
        scholar_query: str | None = None,
    ) -> ResolutionResult:
        parsed = parsed or ParsedReference(raw_input=raw_input)
        query = scholar_query or parsed.title or raw_input
        return ResolutionResult(
            raw_input=raw_input,
            input_kind=input_kind,
            status=ResultStatus.FAILED,
            parsed_title=parsed.title,
            parsed_authors=parsed.authors,
            parsed_year=parsed.year,
            scholar_url=build_scholar_search_url(query),
            message=message,
        )
