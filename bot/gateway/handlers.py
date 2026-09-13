import asyncio
import logging
import re
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from bot import config
from bot.gateway.base import _allowed
from bot.gateway.formatters import send_long_text, send_local_file
from bot.domain.orchestrator import build_context_packet, maybe_update_session_summary
from bot.domain.learning import should_extract, extract_and_merge
from bot.agent.chat_agent import build_chat_agent
from bot.agent.action_registry import parse_action_tags
from bot.agent.response_policy import infer_response_policy
from bot.agent.tools import build_tools
from bot.core.exceptions import BotError

from bot.gateway.commands import *
from bot.gateway.media import *
from bot.gateway.vault import *

logger = logging.getLogger(__name__)
_USER_LOCKS: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

_IMAGE_REQUEST_RE = re.compile(
    r"\b(?:show|send|display|fetch|find|get|give|search|dikhao|dikha|bhejo|bhej|dhoondo|dhundho|lao|la|chahiye|do)\b.*"
    r"\b(?:image|images|photo|photos|pic|pics|picture|pictures|tasveer|tasveer?e|photo+|image+|wallpaper)\b|"
    r"\b(?:image|images|photo|photos|pic|pics|picture|pictures|tasveer|wallpaper)\b.*"
    r"\b(?:show|send|display|fetch|find|get|give|search|dikhao|dikha|bhejo|bhej|dhoondo|dhundho|lao|la|chahiye|do)\b",
    re.IGNORECASE,
)
_LINK_REQUEST_RE = re.compile(
    r"\b(?:link|url|https?://|preview|shareable|share\s+link)\b",
    re.IGNORECASE,
)


def _wants_rag_image_media(text: str) -> bool:
    """Return True for image-display requests, but not explicit link requests."""
    return bool(_IMAGE_REQUEST_RE.search(text)) and not bool(_LINK_REQUEST_RE.search(text))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message or not _allowed(update.effective_user.id):
        return
    uid = update.effective_user.id
    limiter = context.application.bot_data.get("rate_limiter")
    if limiter and not limiter.allow(f"chat:{uid}"):
        await update.message.reply_text("⏳ Thoda slow — ek minute mein bahut zyada requests aa gayi hain.")
        return
    async with _USER_LOCKS[uid]:
        await _handle_text_locked(update, context, uid)


async def _handle_text_locked(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: int):
    user_text = update.message.text or ""
    memory = context.application.bot_data["memory"]
    llm = context.application.bot_data["llm"]
    drive = context.application.bot_data.get("drive")
    rag_tools = context.application.bot_data.get("rag_tools", [])
    rag_mcp = context.application.bot_data.get("rag_mcp")

    ctx = build_context_packet(memory, uid, user_text=user_text)
    history = memory.get_history(uid)
    llm_history = history[-config.LLM_HISTORY_MESSAGES:] if config.LLM_HISTORY_MESSAGES else []
    response_policy = infer_response_policy(user_text, ctx["profile"])
    tools = build_tools(
        memory=memory,
        drive=drive,
        user_id=uid,
        sandbox_path=config.SANDBOX_PATH,
        mcp_tools=rag_tools,
    )
    chain = build_chat_agent(
        llm, tools,
        current_mood=ctx["mood"], user_profile=ctx["profile"],
        session_summary=ctx["session_summary_text"], last_media=ctx["last_media_text"],
        active_fantasy=ctx["fantasy_text"], emotion=ctx["emotion"], time_context=ctx["time_context"],
        memory_context=ctx.get("memory_context_text", ""),
        response_policy=response_policy.to_prompt(),
    )

    try:
        response = await chain.ainvoke({"input": user_text, "chat_history": llm_history})
        for _ in range(2):
            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                break
            tool_map = {tool.name: tool for tool in tools}
            tool_messages = []
            for call in tool_calls:
                tool = tool_map.get(call.get("name"))
                if not tool:
                    logger.error("unknown tool requested name=%s user=%s", call.get("name"), uid)
                    tool_messages.append(ToolMessage(content="Unknown tool", tool_call_id=call.get("id", "unknown")))
                    continue
                try:
                    result = await tool.ainvoke(call.get("args", {}))
                    tool_messages.append(ToolMessage(content=str(result)[:4000], tool_call_id=call.get("id", "unknown")))
                except Exception as exc:
                    logger.exception("tool execution failed name=%s user=%s", call.get("name"), uid)
                    tool_messages.append(ToolMessage(
                        content=f"Tool execution failed ({type(exc).__name__}). Do not pretend it succeeded.",
                        tool_call_id=call.get("id", "unknown"),
                    ))
            response = await chain.ainvoke({
                "input": user_text,
                "chat_history": llm_history + [response] + tool_messages,
            })

        full_reply = getattr(response, "content", None) or str(response)
        clean_reply, actions = parse_action_tags(full_reply)
        clean_reply = clean_reply.strip()

        # Deterministic media guard: for an image-display request, the bot must
        # send the indexed image instead of merely returning a Drive URL. The
        # LLM can still use get_image_link when the user explicitly asks for a link.
        if _wants_rag_image_media(user_text) and rag_mcp and rag_mcp.available:
            if not any(tag == "RAG_SEND_MEDIA" for tag, _ in actions):
                actions.append(("RAG_SEND_MEDIA", user_text))
                logger.info("forced RAG media action for image request user=%s", uid)
    except BotError:
        logger.exception("conversation generation failed user=%s", uid)
        await update.message.reply_text("Is request ka answer abhi complete nahi ho paaya. Thodi der baad try karo.")
        return
    except Exception:
        logger.exception("conversation generation failed user=%s", uid)
        await update.message.reply_text("AI response generate nahi ho paaya. Thodi der mein dobara try karo.")
        return

    history.extend([HumanMessage(content=user_text), AIMessage(content=clean_reply)])
    try:
        memory.save_history(uid, history, config.MAX_HISTORY_MESSAGES)
    except Exception:
        logger.exception("conversation history persistence failed user=%s", uid)

    if clean_reply:
        await send_long_text(update, clean_reply)

    for tag, val in actions:
        try:
            if tag == "VOICE":
                context.args = [clean_reply] if clean_reply else []
                await cmd_voice(update, context)
            elif tag == "VAULT_ADD":
                context.args = [val] if val else []
                await cmd_vault_add(update, context)
            elif tag == "VAULT_LIST":
                await cmd_vault_list(update, context)
            elif tag == "VAULT_OPEN":
                context.args = [val] if val else []
                await cmd_vault_open(update, context)
            elif tag in ("SEND_MEDIA", "DRIVE_GET"):
                if drive and val:
                    await update.message.reply_text("🔎 Search kar rahi hoon…")
                    status, msg = drive.semantic_download(uid, val, config.SANDBOX_PATH)
                    if status == "ok":
                        from bot.gateway.media import _send_media_with_followup
                        await _send_media_with_followup(update, context, msg, uid)
                    else:
                        await update.message.reply_text(msg)
            elif tag == "RAG_SEND_MEDIA":
                rag_mcp = context.application.bot_data.get("rag_mcp")
                if not rag_mcp or not rag_mcp.available or not val:
                    await update.message.reply_text("RAG image search abhi available nahi hai.")
                else:
                    await update.message.reply_text("🧠 Indexed images mein search kar rahi hoon…")
                    path = await rag_mcp.download_top_image(val, config.SANDBOX_PATH)
                    await send_local_file(update, path)
            elif tag == "SET_EMOTION" and val:
                memory.set_emotion(uid, val.lower()[:40])
            elif tag == "EVOLVE" and val:
                profile = memory.get_profile(uid) or {}
                evolutions = profile.get("persona_evolution", [])
                evolutions.append(val[:300])
                profile["persona_evolution"] = evolutions[-8:]
                memory.set_profile(uid, profile)
        except Exception:
            logger.exception("action failed tag=%s user=%s", tag, uid)

    try:
        if should_extract(user_text):
            extract_and_merge(memory, uid, user_text, clean_reply)
    except Exception:
        logger.exception("learning extraction failed user=%s", uid)

    try:
        maybe_update_session_summary(memory, uid)
    except Exception:
        logger.exception("session summary update failed user=%s", uid)
