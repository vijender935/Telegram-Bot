import asyncio
import io
import logging
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from PIL import Image, UnidentifiedImageError

from bot import config
from bot.gateway.base import _allowed
from bot.gateway.formatters import send_long_text
from bot.domain.orchestrator import build_context_packet, maybe_update_session_summary
from bot.domain.learning import should_extract, extract_and_merge
from bot.agent.chat_agent import build_chat_agent
from bot.agent.response_policy import infer_response_policy
from bot.agent.tools import build_tools
from bot.core.exceptions import BotError
from bot.gateway.media import (
    handle_audio,
    handle_document,
    handle_photo,
    handle_video,
    handle_video_note,
    handle_voice,
)

logger = logging.getLogger(__name__)
_USER_LOCKS: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def _tool_result_text(result: object, image_count: int = 0) -> str:
    """Keep MCP image bytes out of the LLM context while preserving useful text."""
    if isinstance(result, (list, tuple)):
        parts = []
        for item in result:
            if isinstance(item, dict) and item.get("type") == "image":
                continue
            if getattr(item, "type", None) == "image":
                continue
            parts.append(_tool_result_text(item, image_count=0))
        text = "\n".join(x for x in parts if x)
    elif isinstance(result, dict):
        safe = {
            k: v for k, v in result.items()
            if k not in {"data"} or result.get("type") != "image"
        }
        text = str(safe)
    else:
        text = str(result)

    if image_count:
        text = (text + "\n" if text else "") + f"{image_count} image(s) retrieved and sent to the user."
    return text[:4000]


async def _send_mcp_images(update: Update, images: list[tuple[bytes, str]]) -> int:
    """Validate/normalize MCP images before sending them through Telegram."""
    sent = 0
    for index, (data, mime_type) in enumerate(images, start=1):
        if not data:
            continue

        filename = f"cloudflare_image_{index}.jpg"
        try:
            # Telegram can return Image_process_failed for valid-looking bytes
            # that are malformed, unsupported, or awkwardly encoded. Decode the
            # actual image first, then normalize it to a standard JPEG payload.
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                width, height = source.size
                if width <= 0 or height <= 0:
                    raise ValueError("invalid image dimensions")
                if source.mode in ("RGBA", "LA", "P"):
                    rgba = source.convert("RGBA")
                    background = Image.new("RGB", rgba.size, "white")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    normalized = background
                else:
                    normalized = source.convert("RGB")

                buffer = io.BytesIO()
                normalized.save(buffer, format="JPEG", quality=92, optimize=True)
                payload = buffer.getvalue()

            if len(payload) > 10 * 1024 * 1024:
                # Do not feed an oversized payload to send_photo. Telegram's
                # document path gives us a safer fallback for large results.
                await update.message.reply_document(
                    document=io.BytesIO(payload),
                    filename=filename,
                )
            else:
                await update.message.reply_photo(
                    photo=io.BytesIO(payload),
                    filename=filename,
                )
            sent += 1
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            logger.warning(
                "MCP image normalization failed index=%s mime=%s bytes=%s error=%s",
                index,
                mime_type,
                len(data),
                exc,
            )
            # Last-resort delivery: if Telegram can accept the bytes as a file,
            # do not lose the image merely because photo processing failed.
            try:
                await update.message.reply_document(
                    document=io.BytesIO(data),
                    filename=f"cloudflare_image_{index}.bin",
                )
                sent += 1
            except Exception:
                logger.exception("MCP image delivery failed index=%s", index)

    return sent


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
    cloudflare_mcp = context.application.bot_data.get("cloudflare_mcp")
    mcp_tools = context.application.bot_data.get("mcp_tools", [])

    ctx = build_context_packet(memory, uid, user_text=user_text)
    history = memory.get_history(uid)
    llm_history = history[-config.LLM_HISTORY_MESSAGES:] if config.LLM_HISTORY_MESSAGES else []
    response_policy = infer_response_policy(user_text, ctx["profile"])
    tools = build_tools(
        memory=memory,
        user_id=uid,
        sandbox_path=config.SANDBOX_PATH,
        mcp_tools=mcp_tools,
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
                    image_count = 0
                    if cloudflare_mcp:
                        images = cloudflare_mcp.extract_images(result)
                        if images:
                            image_count = await _send_mcp_images(update, images)
                            logger.info(
                                "sent %s MCP image(s) directly to Telegram tool=%s user=%s",
                                image_count,
                                call.get("name"),
                                uid,
                            )
                    tool_messages.append(
                        ToolMessage(
                            content=_tool_result_text(result, image_count),
                            tool_call_id=call.get("id", "unknown"),
                        )
                    )
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
        clean_reply = full_reply.strip()
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

    try:
        if should_extract(user_text):
            existing_profile = memory.get_profile(uid) or {}
            new_profile = await extract_and_merge(
                llm, existing_profile, user_text, clean_reply
            )
            memory.set_profile(uid, new_profile)
    except Exception:
        logger.exception("learning extraction failed user=%s", uid)

    try:
        await maybe_update_session_summary(llm, memory, uid, user_text, clean_reply)
    except Exception:
        logger.exception("session summary update failed user=%s", uid)
