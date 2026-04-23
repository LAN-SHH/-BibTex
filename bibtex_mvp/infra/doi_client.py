from __future__ import annotations

from bibtex_mvp.domain.models import CandidateRecord

from .crossref_client import CrossrefClient
from .mapper import map_crossref_item, map_openalex_item
from .openalex_client import OpenAlexClient


class DoiService:
    def __init__(self, crossref_client: CrossrefClient, openalex_client: OpenAlexClient) -> None:
        self.crossref_client = crossref_client
        self.openalex_client = openalex_client

    async def fetch_candidate_by_doi(self, doi: str) -> CandidateRecord | None:
        try:
            crossref_item = await self.crossref_client.fetch_work_by_doi(doi)
        except Exception:
            crossref_item = None
        if crossref_item:
            return map_crossref_item(crossref_item)

        try:
            openalex_item = await self.openalex_client.fetch_work_by_doi(doi)
        except Exception:
            openalex_item = None
        if openalex_item:
            return map_openalex_item(openalex_item)
        return None

    async def fetch_bibtex_by_doi(self, doi: str) -> str | None:
        try:
            return await self.crossref_client.fetch_bibtex(doi)
        except Exception:
            return None
