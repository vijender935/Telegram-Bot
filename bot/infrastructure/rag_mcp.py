"""Client for the user's custom Cloudflare MCP server.

The MCP endpoint is the only remote data/retrieval integration used by the bot.
Tool schemas are discovered from the MCP server at runtime.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from urllib.parse import urlparse

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

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
        """Check health through the custom MCP's discovered health tool."""
        if not self.configured:
            self.last_health = {"status": "disabled"}
            return self.last_health

        health_tool = self.tool_map.get("health")
        if not health_tool:
            self.last_health = {
                "status": "error",
                "error": "Custom Cloudflare MCP did not expose the health tool",
            }
            return self.last_health

        try:
            result = await asyncio.wait_for(health_tool.ainvoke({}), timeout=self.timeout)
            data = self._normalize_health_result(result)
            self.last_health = data
        except Exception as exc:
            self.last_health = {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        return self.last_health

    @classmethod
    def _normalize_health_result(cls, result: object) -> dict[str, object]:
        """Normalize common MCP/LangChain health-tool result shapes."""
        if isinstance(result, dict):
            return result

        content = getattr(result, "content", None)
        if content is not None and content is not result:
            normalized = cls._normalize_health_result(content)
            if normalized:
                return normalized

        if isinstance(result, list):
            for item in result:
                normalized = cls._normalize_health_result(item)
                if normalized:
                    return normalized

        text = getattr(result, "text", None)
        if text:
            return {"status": "ok", "message": str(text)}

        if result is None:
            return {"status": "ok"}

        return {"status": "ok", "result": str(result)}

    async def invoke(self, tool_name: str, args: dict | None = None) -> object:
        """Invoke one dynamically discovered custom MCP tool through LangChain."""
        tool = self.tool_map.get(tool_name)
        if not tool:
            raise RuntimeError(f"Cloudflare MCP tool unavailable: {tool_name}")
        return await asyncio.wait_for(tool.ainvoke(args or {}), timeout=self.timeout)

    async def invoke_raw(self, tool_name: str, args: dict | None = None) -> object:
        """Call the custom MCP server directly and preserve raw MCP content blocks.

        The LangChain adapter can collapse a multimodal MCP result into a plain
        string when a StructuredTool is invoked directly with a normal dict.
        Image retrieval therefore uses the MCP SDK's ClientSession path so the
        original ImageContent block remains available to the Telegram delivery
        layer. This still talks exclusively to the user's custom Cloudflare MCP.
        """
        if not self.configured:
            raise RuntimeError("Cloudflare MCP URL is not configured")

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with streamablehttp_client(self.url, headers=headers) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=self.timeout)
                return await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=args or {}),
                    timeout=self.timeout,
                )

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
                    mime = str(value.get("mimeType") or value.get("mime_type") or "image/jpeg")
                    found.append((raw, mime))
                except Exception:
                    logger.warning("Invalid MCP image content received")

            # Support LangChain standard image blocks as a forward-compatible
            # fallback (data:image/...;base64,...).
            image_url = value.get("image_url")
            if isinstance(image_url, dict):
                url = image_url.get("url")
                if isinstance(url, str) and url.startswith("data:image/") and ";base64," in url:
                    try:
                        header, encoded = url.split(";base64,", 1)
                        raw = base64.b64decode(encoded, validate=True)
                        mime = header[5:] or "image/jpeg"
                        found.append((raw, mime))
                    except Exception:
                        logger.warning("Invalid MCP standard image block received")

            # Some wrappers use base64_data instead of MCP's data field.
            if value.get("base64_data") and value.get("type") == "image":
                try:
                    raw = base64.b64decode(str(value["base64_data"]), validate=True)
                    mime = str(value.get("mimeType") or value.get("mime_type") or "image/jpeg")
                    found.append((raw, mime))
                except Exception:
                    logger.warning("Invalid MCP base64 image artifact received")

            for key, item in value.items():
                if key not in {"data", "base64_data"}:
                    found.extend(cls._find_images(item))
            return found

        if hasattr(value, "type") and getattr(value, "type", None) == "image":
            data = getattr(value, "data", None)
            if data:
                try:
                    raw = base64.b64decode(str(data), validate=True)
                    mime = str(
                        getattr(value, "mimeType", None)
                        or getattr(value, "mime_type", None)
                        or "image/jpeg"
                    )
                    found.append((raw, mime))
                except Exception:
                    logger.warning("Invalid MCP image content object received")
            return found

        # Some MCP adapters wrap non-text MCP content in a ToolMessage
        # artifact instead of putting it in ToolMessage.content. In particular,
        # older langchain-mcp-adapters releases can preserve MCP ImageContent
        # objects in artifact, so inspect both locations.
        artifact = getattr(value, "artifact", None)
        if artifact is not None and artifact is not value:
            found.extend(cls._find_images(artifact))

        content = getattr(value, "content", None)
        if content is not None and content is not value:
            found.extend(cls._find_images(content))
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
