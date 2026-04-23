from __future__ import annotations

from urllib.parse import quote

import httpx


class OpenAlexClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def search_works(self, query: str, per_page: int = 20) -> list[dict]:
        if not query.strip():
            return []
        params = {"search": query, "per-page": per_page}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get("https://api.openalex.org/works", params=params)
                response.raise_for_status()
        except httpx.HTTPError:
            return []
        return response.json().get("results") or []

    async def fetch_work_by_doi(self, doi: str) -> dict | None:
        if not doi:
            return None
        entity = quote(f"https://doi.org/{doi}", safe="")
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"https://api.openalex.org/works/{entity}")
                if response.status_code >= 400:
                    return None
        except httpx.HTTPError:
            return None
        return response.json() or None
