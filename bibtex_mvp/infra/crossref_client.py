from __future__ import annotations

from urllib.parse import quote

import httpx


class CrossrefClient:
    def __init__(self, mailto: str = "bib-mvp@example.com", timeout: float = 10.0) -> None:
        self._headers = {"User-Agent": f"bib-mvp/0.1 (mailto:{mailto})"}
        self._timeout = timeout

    async def search_by_title(self, title: str, rows: int = 20) -> list[dict]:
        if not title.strip():
            return []
        params = {"query.title": title, "rows": rows}
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as client:
            response = await client.get("https://api.crossref.org/works", params=params)
            response.raise_for_status()
        return ((response.json().get("message") or {}).get("items")) or []

    async def search_by_bibliographic(self, reference_text: str, rows: int = 20) -> list[dict]:
        if not reference_text.strip():
            return []
        params = {"query.bibliographic": reference_text, "rows": rows}
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as client:
            response = await client.get("https://api.crossref.org/works", params=params)
            response.raise_for_status()
        return ((response.json().get("message") or {}).get("items")) or []

    async def fetch_work_by_doi(self, doi: str) -> dict | None:
        if not doi:
            return None
        encoded = quote(doi, safe="")
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as client:
            response = await client.get(f"https://api.crossref.org/works/{encoded}")
            if response.status_code >= 400:
                return None
        return (response.json().get("message")) or None

    async def fetch_bibtex(self, doi: str) -> str | None:
        if not doi:
            return None
        encoded = quote(doi, safe="")
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as client:
            response = await client.get(
                f"https://api.crossref.org/works/{encoded}/transform/application/x-bibtex"
            )
            if response.status_code < 400 and response.text.strip().startswith("@"):
                return response.text.strip()

            fallback = await client.get(
                f"https://doi.org/{doi}",
                headers={
                    **self._headers,
                    "Accept": "application/x-bibtex",
                },
                follow_redirects=True,
            )
            if fallback.status_code < 400 and fallback.text.strip().startswith("@"):
                return fallback.text.strip()
        return None

