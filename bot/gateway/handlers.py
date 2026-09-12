import asyncio
import logging
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from bot import config
from bot.gateway.base import _allowed
from bot.gateway.formatters import send_long_text
from bot.domain.orchestrator import build_context_packet, maybe_update_session_summary
from bot.domain.learning import should_extract, extract_and_merge
from bot.agent.chat_agent import build_chat_agent
from bot.agent.action_registry import parse_action_tags
from bot.agent.tools import build_tools
from bot.core.exceptions import BotError

from bot.gateway.commands import *
from bot.gateway.media import *
from bot.gateway.vault import *

logger = logging.getLogger(__name__)
_USER_LOCKS: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


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

    ctx = build_context_packet(memory, uid, user_text=user_text)
    history = memory.get_history(uid)
    history.append(HumanMessage(content=user_text))
    memory.save_history(uid, history, config.MAX_HISTORY_MESSAGES)

    try:
        tools = build_tools(memory=memory, drive=drive, user_id=uid, sandbox_path=config.SANDBOX_PATH)
        chain = build_chat_agent(
            llm, tools,
            current_mood=ctx["mood"], user_profile=ctx["profile"],
            session_summary=ctx["session_summary_text"], last_media=ctx["last_media_text"],
            active_fantasy=ctx["fantasy_text"], emotion=ctx["emotion"], time_context=ctx["time_context"],
        )

        response = await chain.ainvoke({"input": user_text, "chat_history": history[:-1]})
        # Native tool loop: model -> tool -> result -> model. Two rounds prevents runaway execution.
        for _ in range(2):
            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                break
            tool_map = {tool.name: tool for tool in tools}
            tool_messages = []
            for call in tool_calls:
                tool = tool_map.get(call.get("name"))
                if not tool:
                    tool_messages.append(ToolMessage(content="Unknown tool", tool_call_id=call.get("id", "unknown")))
                    continue
                try:
                    result = tool.invoke(call.get("args", {}))
                    tool_messages.append(ToolMessage(content=str(result)[:4000], tool_call_id=call.get("id", "unknown")))
                except Exception as exc:
                    logger.exception("tool execution failed name=%s", call.get("name"))
                    tool_messages.append(ToolMessage(content=f"Tool failed: {type(exc).__name__}", tool_call_id=call.get("id", "unknown")))
            response = await chain.ainvoke({
                "input": user_text,
                "chat_history": history[:-1] + [response] + tool_messages,
            })

        full_reply = getattr(response, "content", None) or str(response)
        clean_reply, actions = parse_action_tags(full_reply)

        if clean_reply:
            history.append(AIMessage(content=clean_reply))
            memory.save_history(uid, history, config.MAX_HISTORY_MESSAGES)
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
                elif tag == "SET_EMOTION" and val:
                    memory.set_emotion(uid, val.lower()[:40])
                elif tag == "EVOLVE" and val:
                    profile = memory.get_profile(uid) or {}
                    evolutions = profile.get("persona_evolution", [])
                    evolutions.append(val[:300])
                    profile["persona_evolution"] = evolutions[-8:]
                    memory.set_profile(uid, profile)
            except Exception:
                logger.exception("action failed tag=%s", tag)

        if should_extract(user_text):
            memory.set_profile(uid, await extract_and_merge(llm, ctx["profile"], user_text, clean_reply))
        await maybe_update_session_summary(llm, memory, uid, user_text, clean_reply)

    except BotError:
        logger.exception("expected bot error")
        await update.message.reply_text("Request complete nahi ho paayi. Thodi der baad try karo.")
    except Exception:
        logger.exception("chat failed")
        await update.message.reply_text("Abhi AI service busy hai. Thodi der mein dobara try karo.")
