"""Resilient client for the remote multimodal RAG MCP server."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


class RAGMCPClient:
    """Loads remote MCP tools without making the bot dependent on RAG availability."""

    def __init__(
        self,
        url: str,
        *,
        api_key: str = "",
        timeout: float = 20.0,
        top_k: int = 5,
        mode: str = "hybrid",
        retries: int = 3,
    ) -> None:
        self.url = url.strip()
        self.api_key = api_key.strip()
        self.timeout = max(3.0, float(timeout))
        self.top_k = max(1, min(int(top_k), 30))
        self.mode = mode if mode in {"metadata", "visual", "hybrid"} else "hybrid"
        self.retries = max(1, min(int(retries), 5))
        self.client: MultiServerMCPClient | None = None
        self.tools: list[BaseTool] = []
        self.tool_map: dict[str, BaseTool] = {}
        self.available = False
        self.last_error = ""
        self.last_health: dict[str, object] = {}

    @property
    def configured(self) -> bool:
        return bool(self.url)

    async def initialize(self) -> list[BaseTool]:
        """Discover MCP tools with bounded retries and graceful degradation."""
        if not self.configured:
            self.last_error = "RAG MCP URL is not configured"
            return []

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        self.available = False
        self.tools = []
        self.tool_map = {}
        last_error = ""

        for attempt in range(1, self.retries + 1):
            try:
                self.client = MultiServerMCPClient(
                    {
                        "rag": {
                            "transport": "streamable_http",
                            "url": self.url,
                            "headers": headers,
                        }
                    }
                )
                tools = await asyncio.wait_for(self.client.get_tools(), timeout=self.timeout)
                self.tools = tools
                self.tool_map = {tool.name: tool for tool in tools}
                self.available = bool(tools)
                self.last_error = "" if self.available else "MCP endpoint returned no tools"
                if self.available:
                    logger.info("RAG MCP ready tools=%s", sorted(self.tool_map))
                    return tools
                last_error = self.last_error
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "RAG MCP discovery attempt %s/%s failed url=%s error=%s",
                    attempt,
                    self.retries,
                    self._safe_url(),
                    last_error,
                )
            if attempt < self.retries:
                await asyncio.sleep(min(2 ** (attempt - 1), 4))

        self.last_error = last_error or "RAG MCP discovery failed"
        logger.warning("RAG MCP unavailable url=%s error=%s", self._safe_url(), self.last_error)
        return []

    async def health(self) -> dict[str, object]:
        """Check the MCP service health endpoint without creating an MCP session."""
        if not self.configured:
            self.last_health = {"status": "disabled"}
            return self.last_health
        parsed = urlparse(self.url)
        health_url = urlunparse(parsed._replace(path=parsed.path.rstrip("/")[:-3] + "/health" if parsed.path.endswith("/mcp") else parsed.path.rstrip("/") + "/health", query="", fragment=""))
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(health_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                self.last_health = data if isinstance(data, dict) else {"status": "ok"}
        except Exception as exc:
            self.last_health = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        return self.last_health

    async def invoke(self, tool_name: str, args: dict) -> object:
        """Invoke a discovered MCP tool with a bounded timeout."""
        tool = self.tool_map.get(tool_name)
        if not tool:
            raise RuntimeError(f"RAG MCP tool unavailable: {tool_name}")
        return await asyncio.wait_for(tool.ainvoke(args), timeout=self.timeout)

    async def search_images(
        self,
        query: str,
        *,
        top_k: int | None = None,
        mode: str | None = None,
    ) -> dict:
        result = await self.invoke(
            "search_images",
            {
                "query": query,
                "top_k": top_k or self.top_k,
                "mode": mode or self.mode,
            },
        )
        if isinstance(result, dict):
            return result
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
            raise RuntimeError(result)
        raise RuntimeError("RAG returned an unsupported search result")

    async def download_top_image(self, query: str, destination_dir: str | Path) -> Path:
        """Search RAG and download the highest-ranked Drive image locally."""
        result = await self.search_images(query, top_k=1)
        results = result.get("results") if isinstance(result, dict) else None
        if not results:
            raise FileNotFoundError("RAG did not find a matching image")
        item = results[0]
        image_url = item.get("image_url") or item.get("preview_url")
        if not image_url:
            drive_file_id = item.get("drive_file_id")
            if drive_file_id:
                link = await self.invoke("get_image_link", {"drive_file_id": drive_file_id})
                if isinstance(link, dict):
                    image_url = link.get("view_link") or link.get("preview_link")
        if not image_url:
            raise FileNotFoundError("RAG result has no downloadable image URL")

        filename = Path(str(item.get("file_name") or "rag_result.jpg")).name
        if Path(filename).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
            filename += ".jpg"
        destination = Path(destination_dir)
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / filename
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            if not response.content:
                raise RuntimeError("RAG image response was empty")
            target.write_bytes(response.content)
        return target

    def _safe_url(self) -> str:
        try:
            parsed = urlparse(self.url)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        except Exception:
            return "<invalid-url>"
