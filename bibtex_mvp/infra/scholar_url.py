from __future__ import annotations

from urllib.parse import urlencode


def build_scholar_search_url(query: str) -> str:
    params = urlencode({"q": query})
    return f"https://scholar.google.com/scholar?{params}"

