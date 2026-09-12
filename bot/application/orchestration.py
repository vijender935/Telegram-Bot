"""Provider-agnostic orchestration facade.

This is the migration seam toward a real plan -> tool -> result -> response agent.
The existing handlers can keep their Telegram-specific UX while execution moves here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: Any = None
    error: str | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        if not name or "." not in name:
            raise ValueError("Tool names must use namespace.operation")
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = fn

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def execute(self, call: ToolCall) -> ToolResult:
        fn = self._tools.get(call.name)
        if fn is None:
            return ToolResult(False, error=f"Unknown tool: {call.name}")
        try:
            return ToolResult(True, data=fn(**call.arguments))
        except Exception as exc:
            return ToolResult(False, error=type(exc).__name__)
