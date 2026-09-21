"""Provider-facing chat service shared by external API clients and Telegram."""
from __future__ import annotations

import asyncio
from langchain_core.messages import HumanMessage, AIMessage

from bot import config
from bot.agent.chat_agent import build_chat_agent_with_components
from bot.agent.response_policy import infer_response_policy
from bot.agent.tools import build_tools
from bot.domain.orchestrator import build_context_packet

class ChatService:
    def __init__(self, memory, llm, mcp_tools=None):
        self.memory = memory
        self.llm = llm
        self.mcp_tools = list(mcp_tools or [])

    async def reply(self, user_id: int, text: str) -> str:
        text = (text or "").strip()
        if not text:
            raise ValueError("message must not be empty")
        ctx = build_context_packet(self.memory, user_id, user_text=text)
        history = self.memory.get_history(user_id)
        llm_history = history[-config.LLM_HISTORY_MESSAGES:] if config.LLM_HISTORY_MESSAGES else []
        public_tools = [t for t in self.mcp_tools if getattr(t, "name", "") != "get_image"]
        tools = build_tools(memory=self.memory, user_id=user_id, sandbox_path=config.SANDBOX_PATH, mcp_tools=public_tools)
        policy = infer_response_policy(text, ctx.get("profile")).to_prompt()
        chain, system_message, model = build_chat_agent_with_components(
            self.llm, tools,
            user_profile=ctx.get("profile"),
            session_summary=ctx.get("session_summary_text", ""),
            last_media=ctx.get("last_media_text", ""),
            time_context=ctx.get("time_context", ""),
            memory_context=ctx.get("memory_context_text", ""),
            response_policy=policy,
        )
        response = await asyncio.wait_for(chain.ainvoke({"input": text, "chat_history": llm_history}), timeout=config.AI_REQUEST_TIMEOUT_SECONDS)
        # External API deliberately returns text only. Media delivery remains a Telegram concern.
        for _ in range(config.MAX_TOOL_ROUNDS):
            calls = getattr(response, "tool_calls", None) or []
            if not calls:
                break
            tool_map = {t.name: t for t in tools}
            from langchain_core.messages import ToolMessage
            results = []
            for call in calls:
                tool = tool_map.get(call.get("name"))
                if not tool:
                    results.append(ToolMessage(content="Unknown tool", tool_call_id=call.get("id", "unknown")))
                    continue
                try:
                    result = await asyncio.wait_for(tool.ainvoke(call.get("args") or {}), timeout=config.TOOL_TIMEOUT_SECONDS)
                    results.append(ToolMessage(content=str(result)[:6000], tool_call_id=call.get("id", "unknown")))
                except Exception as exc:
                    results.append(ToolMessage(content=f"Tool failed: {type(exc).__name__}", tool_call_id=call.get("id", "unknown")))
            response = await asyncio.wait_for(model.ainvoke([system_message, *llm_history, HumanMessage(content=text), response, *results]), timeout=config.AI_REQUEST_TIMEOUT_SECONDS)
        answer = str(getattr(response, "content", "") or "").strip()
        if not answer:
            answer = "Request complete nahi ho paaya. Dobara try karo."
        history.extend([HumanMessage(content=text), AIMessage(content=answer)])
        self.memory.save_history(user_id, history, config.MAX_HISTORY_MESSAGES)
        return answer
