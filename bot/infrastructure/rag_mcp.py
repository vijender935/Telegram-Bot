"""Client for the user's custom Cloudflare MCP server.

The MCP endpoint is the only remote data/retrieval integration used by the bot.
Tool schemas are discovered from the MCP server at runtime.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


class CloudflareMCPClient:
    """Discover and invoke the user's custom Cloudflare MCP tools."""

    def __init__(
        self,
        url: str,
        *,
        api_key: str = "",
        timeout: float = 30.0,
        retries: int = 3,
    ) -> None:
        self.url = url.strip()
        self.api_key = api_key.strip()
        self.timeout = max(3.0, float(timeout))
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
        if not self.configured:
            self.last_error = "Cloudflare MCP URL is not configured"
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
                        "cloudflare": {
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
                    logger.info("Cloudflare MCP ready tools=%s", sorted(self.tool_map))
                    return tools
                last_error = self.last_error
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Cloudflare MCP discovery attempt %s/%s failed url=%s error=%s",
                    attempt,
                    self.retries,
                    self._safe_url(),
                    last_error,
                )
            if attempt < self.retries:
                await asyncio.sleep(min(2 ** (attempt - 1), 4))

        self.last_error = last_error or "Cloudflare MCP discovery failed"
        logger.warning("Cloudflare MCP unavailable url=%s error=%s", self._safe_url(), self.last_error)
        return []

    async def health(self) -> dict[str, object]:
        """Check the custom MCP's upstream Worker health endpoint."""
        if not self.configured:
            self.last_health = {"status": "disabled"}
            return self.last_health

        parsed = urlparse(self.url)
        if parsed.path.endswith("/mcp"):
            health_path = parsed.path[:-4] + "/health"
        else:
            health_path = parsed.path.rstrip("/") + "/health"
        health_url = urlunparse(parsed._replace(path=health_path, query="", fragment=""))
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

    async def invoke(self, tool_name: str, args: dict | None = None) -> object:
        """Invoke one dynamically discovered custom MCP tool."""
        tool = self.tool_map.get(tool_name)
        if not tool:
            raise RuntimeError(f"Cloudflare MCP tool unavailable: {tool_name}")
        return await asyncio.wait_for(tool.ainvoke(args or {}), timeout=self.timeout)

    @staticmethod
    def _field(value: object, name: str) -> object:
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    @classmethod
    def _find_images(cls, value: object) -> list[tuple[bytes, str]]:
        """Extract MCP image content recursively from an adapter result."""
        found: list[tuple[bytes, str]] = []
        if isinstance(value, (list, tuple)):
            for item in value:
                found.extend(cls._find_images(item))
            return found

        if isinstance(value, dict):
            if value.get("type") == "image" and value.get("data"):
                try:
                    raw = base64.b64decode(str(value["data"]), validate=True)
                    mime = str(value.get("mimeType") or "image/jpeg")
                    found.append((raw, mime))
                except Exception:
                    logger.warning("Invalid MCP image content received")
            for key, item in value.items():
                if key not in {"data"}:
                    found.extend(cls._find_images(item))
            return found

        if hasattr(value, "type") and getattr(value, "type", None) == "image":
            data = getattr(value, "data", None)
            if data:
                try:
                    raw = base64.b64decode(str(data), validate=True)
                    mime = str(getattr(value, "mimeType", None) or "image/jpeg")
                    found.append((raw, mime))
                except Exception:
                    logger.warning("Invalid MCP image content object received")
        return found

    @classmethod
    def extract_images(cls, result: object) -> list[tuple[bytes, str]]:
        return cls._find_images(result)

    @staticmethod
    def extension_for_mime(mime_type: str) -> str:
        return {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
        }.get(mime_type.lower(), ".jpg")

    def _safe_url(self) -> str:
        try:
            parsed = urlparse(self.url)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        except Exception:
            return "<invalid-url>"
