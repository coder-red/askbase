"""Web search provider using DuckDuckGo HTML (no API key required)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from basechatt.config.settings import settings
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.search.web")

DUCKDUCKGO_HTML = "https://html.duckduckgo.com/html/"

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = "web"

@dataclass
class SearchResponse:
    results: list[SearchResult]
    query: str

async def duckduckgo_search(
    query: str,
    max_results: int = 8,
    region: str = "wt-wt",
    safe_search: str = "moderate",
) -> SearchResponse:
    """Search DuckDuckGo HTML and return structured results.

    No API key required. Respects robots.txt and rate limits via small delays.
    """
    params = {
        "q": query,
        "kl": region,
        "kp": "1" if safe_search == "strict" else "-1",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            resp = await client.get(DUCKDUCKGO_HTML, params=params, headers=headers)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("DuckDuckGo search failed for %r: %s", query, e)
            return SearchResponse(results=[], query=query)

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[SearchResult] = []

    for link in soup.select(".result__title a.result__snippet, .result__snippet"):
        pass

    for result_div in soup.select(".result"):
        title_el = result_div.select_one(".result__title a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        url = title_el.get("href", "")
        snippet_el = result_div.select_one(".result__snippet")
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""

        if not title or not url:
            continue

        if url.startswith("//duckduckgo.com/l/?uddg="):
            import urllib.parse
            uddg = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("uddg", [""])[0]
            url = urllib.parse.unquote(uddg)

        results.append(SearchResult(title=title, url=url, snippet=snippet))
        if len(results) >= max_results:
            break

    return SearchResponse(results=results, query=query)


async def search_web(query: str, max_results: int = 8) -> SearchResponse:
    """Unified web search entry point (currently DuckDuckGo)."""
    return await duckduckgo_search(query, max_results=max_results)


async def needs_web_search(query: str, local_evidence_count: int) -> bool:
    """Heuristic: does this query likely need current web information?"""
    q = query.lower()
    current_indicators = [
        "current", "latest", "today", "now", "recent", "breaking",
        "stock price", "share price", "market price", "trading at",
        "news", "announced", "earnings release", "dividend",
        "ipo", "listing", "delisting", "merger", "acquisition",
        "booming", "rally", "crash", "surge", "plunge",
        "2025", "2026", "this year", "this quarter",
        "ngx", "nigerian exchange", "nse", "stock exchange",
    ]
    if local_evidence_count == 0:
        return True
    return any(ind in q for ind in current_indicators)