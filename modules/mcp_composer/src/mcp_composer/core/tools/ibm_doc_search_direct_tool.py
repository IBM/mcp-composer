"""IBM Doc Search Direct Tool — searches IBM docs API and returns full page content as markdown."""

import asyncio
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from fastmcp.tools import Tool
from fastmcp.tools import ToolResult
from mcp.types import TextContent
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from markdownify import markdownify as md
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

CONTENT_API_URL = "https://www.ibm.com/docs/api/v1/content"
SEARCH_API_URL = "https://www.ibm.com/docs/api/v1/search"
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}
EXCLUDED_TAGS = {"nav", "footer", "header", "aside", "form", "iframe", "noscript"}

GENERIC_ERROR_MESSAGE = (
    "The IBM documentation search could not complete. "
    "Try again later or rephrase your query."
)


class IBMDocSearchInput(BaseModel):
    """Input schema for the IBM Doc Search tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        description="Search query for IBM docs (e.g. 'kubernetes deployment', 'MQ configuration')"
    )
    max_results: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of doc pages to return (1-5). Defaults to 3.",
    )


class IBMDocSearchDirectTool(Tool):
    """
    Search IBM documentation and return relevant pages as markdown context.
    Uses IBM docs search API and content API directly.
    """

    _products: list[str] = PrivateAttr(default_factory=list)
    _lang: str = PrivateAttr(default="en")
    _timeout: int = PrivateAttr(default=50)
    _preferred_product_paths: list[str] = PrivateAttr(default_factory=list)

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        name: str = "ibm_doc_search_direct",
        products: str | None = None,
        max_results: int = 3,
        language: str = "en",
        timeout: int = 50,
        preferred_product_paths: list[str] | None = None,
    ):
        config = config or {}
        products_raw = products or config.get("products", "")
        parameters = IBMDocSearchInput.model_json_schema()
        super().__init__(
            name=config.get("name", name),
            description=(
                "Search IBM documentation via IBM docs search API and return full page content as markdown. "
                "A single call searches the IBM docs API, fetches up to max_results "
                "full pages, and returns their complete content. Do NOT call multiple "
                "times for the same topic. Use this tool to answer questions about IBM product documentation, "
                "how-to guides, configuration options, and feature explanations."
            ),
            parameters=parameters,
        )
        self._products = [
            p.strip().lower() for p in products_raw.split(",") if p.strip()
        ]
        self._lang = config.get("language", language) or "en"
        self._timeout = config.get("timeout", timeout) or 50
        raw = preferred_product_paths or config.get("preferred_product_paths")
        self._preferred_product_paths = (
            list(raw) if isinstance(raw, list) and raw else ["watsonx/w-and-w", "2.3"]
        )

    def _score_url_version(self, url: str) -> tuple[int, int, int]:
        """Return sort key (higher = preferred). Prefer newer versions and preferred product paths."""
        path = urlparse(url).path.lower()
        has_preferred = (
            1 if any(p in path for p in self._preferred_product_paths) else 0
        )
        match = re.search(r"(\d+)\.(\d+)(?:\.\w+)?", path)
        major, minor = (int(match.group(1)), int(match.group(2))) if match else (0, 0)
        return (has_preferred, major, minor)

    def _extract_link(self, t: dict[str, Any]) -> dict[str, Any] | None:
        """Extract link dict from topic with safe access."""
        url = t.get("fullurl") or t.get("url")
        if not url:
            return None
        title = (t.get("title") or "").replace("<b>", "").replace("</b>", "")
        snippet = (t.get("snippet") or "").replace("<b>", "").replace("</b>", "")
        product = t.get("product") or {}
        product_label = product.get("label", "") if isinstance(product, dict) else ""
        return {
            "title": title or "Untitled",
            "url": url,
            "href": t.get("href", ""),
            "snippet": snippet,
            "product": product_label,
        }

    async def _search(self, query: str, max_results: int) -> str:
        max_results = min(max(max_results, 1), 5)
        t_start = time.perf_counter()

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers={**HTTP_HEADERS, "Accept": "application/json"},
            ) as client:
                resp = await client.get(
                    SEARCH_API_URL,
                    params={
                        "query": query,
                        "lang": self._lang,
                        "limit": max_results * (5 if self._products else 3),
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as e:
            logger.warning("IBM docs search timeout: %s", e)
            raise
        except httpx.ConnectError as e:
            logger.warning("IBM docs search connection error: %s", e)
            raise
        except httpx.HTTPStatusError as e:
            logger.warning(
                "IBM docs search HTTP error: %s %s", e.response.status_code, e
            )
            raise
        except ValueError as e:
            logger.warning("IBM docs search invalid JSON: %s", e)
            raise

        topics = data.get("topics", [])
        if not isinstance(topics, list):
            logger.warning("IBM docs search: topics is not a list")
            return "No results found."

        links = []
        for t in topics:
            if not isinstance(t, dict):
                continue
            link = self._extract_link(t)
            if link:
                links.append(link)

        # Sort by version preference (newer and preferred product paths first)
        links.sort(
            key=lambda L: self._score_url_version(L.get("url", "")),
            reverse=True,
        )

        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for link in links:
            url = link.get("url")
            if not url:
                continue
            parsed = urlparse(url)
            path_parts = parsed.path.split("/")
            normalized = "/".join(
                p for p in path_parts if not any(c.isdigit() and "." in p for c in p)
            )
            if normalized not in seen:
                seen.add(normalized)
                unique.append(link)
        links = unique

        total_before = len(links)
        if self._products:
            links = [
                link
                for link in links
                if any(p in link.get("product", "").lower() for p in self._products)
            ]

        links = links[:max_results]

        if not links:
            if self._products and total_before > 0:
                return (
                    f"No results found for product(s): {', '.join(self._products)}. "
                    f"The search returned {total_before} result(s) but none matched "
                    f"the configured product filter. Do NOT retry with a different query — "
                    f"the IBM documentation may not have content for this topic under the "
                    f"specified product(s)."
                )
            return "No results found."

        async def fetch_one(
            client: httpx.AsyncClient, link: dict[str, Any]
        ) -> tuple[str, str]:
            url = link.get("url", "")
            href = link.get("href", "")
            if not url:
                return "", "[Error: missing URL]"
            try:
                content_url = f"{CONTENT_API_URL}/{href}" if href else url
                resp = await client.get(content_url, follow_redirects=True)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup.find_all(EXCLUDED_TAGS):
                    tag.decompose()
                body = soup.select_one("body") or soup
                return url, md(str(body), strip=["img"]).strip()
            except httpx.TimeoutException:
                return url, "[Error: request timed out]"
            except httpx.HTTPStatusError as e:
                return url, f"[Error: HTTP {e.response.status_code}]"
            except Exception as e:
                logger.debug("Error fetching page %s: %s", url, e)
                return url, f"[Error fetching page: {e}]"

        async with httpx.AsyncClient(
            timeout=self._timeout,
            headers={**HTTP_HEADERS, "Accept": "text/html"},
        ) as client:
            tasks = [fetch_one(client, link) for link in links]
            pairs = await asyncio.gather(*tasks)

        pages = dict(pairs)

        parts = []
        for link in links:
            url = link["url"]
            content = pages.get(url, "")
            parts.append(
                f"# {link['title']}\n"
                f"**Source:** {url}\n"
                f"**Product:** {link['product']}\n\n"
                f"{content}\n"
            )
        context = "\n---\n\n".join(parts)
        elapsed = time.perf_counter() - t_start
        sources_list = "\n".join(f"- {link['url']}" for link in links)
        header = (
            f"**IBM Docs Search Results** — {len(pages)} page(s) returned "
            f'for query: "{query}" ({elapsed:.1f}s).\n\n'
            f"**Sources used:**\n{sources_list}\n\n"
            f"This response contains the full content of all matched pages. "
            f"Do not call this tool again for the same topic.\n\n"
        )
        return header + context

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            validated = IBMDocSearchInput.model_validate(arguments)
        except Exception as e:
            logger.warning("Invalid arguments for ibm_doc_search_direct: %s", e)
            return ToolResult(
                content=[TextContent(type="text", text=GENERIC_ERROR_MESSAGE)],
            )

        try:
            result = await self._search(
                query=validated.query,
                max_results=validated.max_results,
            )
            return ToolResult(content=[TextContent(type="text", text=result)])
        except httpx.TimeoutException:
            logger.warning("IBM doc search timeout for query: %s", validated.query)
            return ToolResult(
                content=[TextContent(type="text", text=GENERIC_ERROR_MESSAGE)]
            )
        except httpx.ConnectError:
            logger.warning(
                "IBM doc search connection error for query: %s", validated.query
            )
            return ToolResult(
                content=[TextContent(type="text", text=GENERIC_ERROR_MESSAGE)]
            )
        except httpx.HTTPStatusError as e:
            logger.warning("IBM doc search HTTP error: %s", e)
            return ToolResult(
                content=[TextContent(type="text", text=GENERIC_ERROR_MESSAGE)]
            )
        except ValueError as e:
            logger.warning("IBM doc search parse error: %s", e)
            return ToolResult(
                content=[TextContent(type="text", text=GENERIC_ERROR_MESSAGE)]
            )
        except Exception as e:
            logger.exception("IBM doc search failed: %s", e)
            return ToolResult(
                content=[TextContent(type="text", text=GENERIC_ERROR_MESSAGE)],
            )
