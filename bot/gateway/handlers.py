import asyncio
import json
import logging
import re
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from bot import config
from bot.gateway.formatters import send_long_text
from bot.domain.orchestrator import build_context_packet, maybe_update_session_summary
from bot.domain.learning import should_extract, extract_and_merge
from bot.agent.chat_agent import build_chat_agent_with_components, build_groq_llm
from bot.agent.response_policy import infer_response_policy
from bot.agent.tools import build_tools
from bot.core.exceptions import BotError
from bot.gateway.mcp_media import extract_r2_keys, send_mcp_images

logger = logging.getLogger(__name__)
_USER_LOCKS: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def _strip_tool_image_markup(text: str) -> str:
    """Remove image markdown/base64 payloads emitted by MCP tools."""
    # MCP image markdown can contain a very long base64 path and may be
    # truncated before the closing ')'. Strip the whole image payload.
    text = re.sub(
        r"!\[[^\]]*\]\((?:/|data:image/)[\s\S]*",
        "",
        text,
    )
    text = re.sub(
        r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+",
        "",
        text,
    )
    return text.strip()


def _tool_result_text(result: object, image_count: int = 0) -> str:
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

    text = _strip_tool_image_markup(text)
    if image_count:
        text = (text + "\n" if text else "") + f"{image_count} image(s) retrieved and sent to the user."
    return text[:4000]


def _llm_tool_result(
    result: object,
    tool_name: str,
    image_count: int = 0,
    r2_key_count: int = 0,
) -> str:
    """Build an LLM-safe summary; never expose MCP media payloads to the model."""
    if tool_name == "search_images":
        summary = f"search_images completed; {r2_key_count} matching image object(s) found."
        if image_count:
            summary += f" {image_count} image(s) were delivered to the user."
        elif r2_key_count:
            summary += " The matching image could not be delivered."
        return summary

    if tool_name == "get_image":
        if image_count:
            return f"get_image completed; {image_count} image(s) were delivered to the user."
        return "get_image completed, but no image was available for delivery."

    if image_count:
        return (
            f"{tool_name} completed; {image_count} image(s) were delivered to the user. "
            "Image binary/base64 content is intentionally not included in the tool result."
        )

    return _tool_result_text(result)


def _extract_tool_calls(response: object) -> list[dict]:
    calls = getattr(response, "tool_calls", None) or []
    if calls:
        return [dict(call) for call in calls]

    additional = getattr(response, "additional_kwargs", None) or {}
    raw_calls = additional.get("tool_calls") or []
    normalized: list[dict] = []
    for raw in raw_calls:
        if not isinstance(raw, dict):
            continue
        function = raw.get("function") or {}
        args = function.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                logger.warning("Invalid tool-call arguments received: %s", args)
                args = {}
        normalized.append({
            "id": raw.get("id") or "unknown",
            "name": function.get("name") or raw.get("name"),
            "args": args if isinstance(args, dict) else {},
        })
    return normalized


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
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
    cloudflare_mcp = context.application.bot_data.get("cloudflare_mcp")
    mcp_tools = context.application.bot_data.get("mcp_tools", [])

    logger.info("groq path user=%s", uid)

    ctx = build_context_packet(memory, uid, user_text=user_text)
    history = memory.get_history(uid)
    llm_history = history[-config.LLM_HISTORY_MESSAGES:] if config.LLM_HISTORY_MESSAGES else []

    clean_reply = await _run_tools_path(
        update, context, uid, user_text, ctx, llm_history, memory,
        cloudflare_mcp, mcp_tools,
    )

    if clean_reply is None:
        return

    history.extend([HumanMessage(content=user_text), AIMessage(content=clean_reply)])
    try:
        memory.save_history(uid, history, config.MAX_HISTORY_MESSAGES)
    except Exception:
        logger.exception("conversation history persistence failed user=%s", uid)

    if clean_reply:
        await send_long_text(update, clean_reply)

    # Learning + session summary use Groq (stable, cheap)
    try:
        groq_llm = context.application.bot_data.get("llm") or build_groq_llm()
        if should_extract(user_text):
            existing_profile = memory.get_profile(uid) or {}
            new_profile = await extract_and_merge(
                groq_llm, existing_profile, user_text, clean_reply
            )
            memory.set_profile(uid, new_profile)
    except Exception:
        logger.exception("learning extraction failed user=%s", uid)

    try:
        groq_llm = context.application.bot_data.get("llm") or build_groq_llm()
        await maybe_update_session_summary(groq_llm, memory, uid, user_text, clean_reply)
    except Exception:
        logger.exception("session summary update failed user=%s", uid)


async def _execute_tool_calls(
    update,
    uid: int,
    response,
    tools,
    tool_model,
    system_message,
    llm_history,
    user_text: str,
    cloudflare_mcp,
) -> tuple[object, int]:
    executed_tool_results: dict[tuple[str, str], object] = {}
    delivered_r2_keys: set[str] = set()
    delivered_images_total = 0

    for _ in range(6):
        tool_calls = _extract_tool_calls(response)
        logger.info(
            "groq tool loop user=%s calls=%s",
            uid,
            [call.get("name") for call in tool_calls],
        )
        if not tool_calls:
            break

        tool_map = {tool.name: tool for tool in tools}
        tool_messages = []
        for call in tool_calls:
            tool = tool_map.get(call.get("name"))
            if not tool:
                logger.error("unknown tool requested name=%s user=%s", call.get("name"), uid)
                tool_messages.append(
                    ToolMessage(
                        content="Unknown tool",
                        tool_call_id=call.get("id", "unknown"),
                    )
                )
                continue

            try:
                call_args = call.get("args", {})
                try:
                    call_signature = (
                        call.get("name", ""),
                        json.dumps(
                            call_args,
                            sort_keys=True,
                            separators=(",", ":"),
                            default=str,
                        ),
                    )
                except (TypeError, ValueError):
                    call_signature = (call.get("name", ""), repr(call_args))

                cached_result = executed_tool_results.get(call_signature)
                if cached_result is not None:
                    result = cached_result
                else:
                    result = await tool.ainvoke(call_args)
                    executed_tool_results[call_signature] = result

                image_count = 0
                r2_keys: list[str] = []
                tool_name = call.get("name") or ""
                if cloudflare_mcp:
                    images = cloudflare_mcp.extract_images(result)
                    if images:
                        image_count = await send_mcp_images(update, images)
                        delivered_images_total += image_count

                    if tool_name == "search_images":
                        r2_keys = extract_r2_keys(result)
                        if r2_keys:
                            try:
                                image_result = await cloudflare_mcp.invoke_raw(
                                    "get_image", {"key": r2_keys[0]}
                                )
                                fetched = cloudflare_mcp.extract_images(image_result)
                                if fetched:
                                    key = r2_keys[0]
                                    if key not in delivered_r2_keys:
                                        # Image-only delivery: do not generate or attach a caption.
                                        delivered = await send_mcp_images(
                                            update, fetched, caption=None
                                        )
                                        if delivered:
                                            delivered_r2_keys.add(key)
                                        image_count += delivered
                                        delivered_images_total += delivered
                            except Exception:
                                logger.exception("automatic get_image failed key=%s", r2_keys[0])

                tool_messages.append(
                    ToolMessage(
                        content=_llm_tool_result(
                            result,
                            tool_name,
                            image_count=image_count,
                            r2_key_count=len(r2_keys),
                        ),
                        tool_call_id=call.get("id", "unknown"),
                    )
                )
            except Exception as exc:
                logger.exception(
                    "tool execution failed name=%s user=%s",
                    call.get("name"),
                    uid,
                )
                tool_messages.append(
                    ToolMessage(
                        content=(
                            f"Tool execution failed ({type(exc).__name__}). "
                            "Do not pretend it succeeded."
                        ),
                        tool_call_id=call.get("id", "unknown"),
                    )
                )

        response = await tool_model.ainvoke(
            [
                system_message,
                *llm_history,
                HumanMessage(content=user_text),
                response,
                *tool_messages,
            ]
        )

    return response, delivered_images_total


async def _run_tools_path(
    update, context, uid, user_text, ctx, llm_history, memory,
    cloudflare_mcp, mcp_tools,
) -> str | None:
    """Single Groq path — assistant + tools."""
    llm = context.application.bot_data.get("llm") or build_groq_llm()
    response_policy = infer_response_policy(user_text, ctx["profile"])
    # get_image is an internal media-delivery primitive. Groq should not
    # see or call it directly; search_images is the public retrieval tool.
    public_mcp_tools = [
        tool for tool in mcp_tools
        if getattr(tool, "name", "") != "get_image"
    ]
    tools = build_tools(
        memory=memory,
        user_id=uid,
        sandbox_path=config.SANDBOX_PATH,
        mcp_tools=public_mcp_tools,
    )
    logger.info(
        "groq tools user=%s count=%s names=%s",
        uid,
        len(tools),
        [getattr(tool, "name", type(tool).__name__) for tool in tools],
    )
    chain, system_message, tool_model = build_chat_agent_with_components(
        llm, tools,
        user_profile=ctx["profile"],
        session_summary=ctx["session_summary_text"],
        last_media=ctx["last_media_text"],
        time_context=ctx["time_context"],
        memory_context=ctx.get("memory_context_text", ""),
        response_policy=response_policy.to_prompt(),
    )

    try:
        response = await chain.ainvoke(
            {"input": user_text, "chat_history": llm_history}
        )
        initial_tool_calls = _extract_tool_calls(response)
        logger.info(
            "groq initial response user=%s type=%s tool_calls=%s content=%r",
            uid,
            type(response).__name__,
            [call.get("name") for call in initial_tool_calls],
            str(getattr(response, "content", ""))[:500],
        )
        response, delivered_images = await _execute_tool_calls(
            update,
            uid,
            response,
            tools,
            tool_model,
            system_message,
            llm_history,
            user_text,
            cloudflare_mcp,
        )

        # Successful image delivery is already the user-facing result.
        # Do not let the model append canned follow-up suggestions.
        if delivered_images:
            return ""

        full_reply = getattr(response, "content", None)
        clean_reply = str(full_reply).strip() if full_reply else ""
        if not clean_reply:
            remaining_calls = _extract_tool_calls(response)
            if remaining_calls:
                clean_reply = "Tool operation complete nahi ho paaya. Ek baar dobara try karo."
            else:
                clean_reply = "hmm bol na."
        return clean_reply

    except BotError:
        logger.exception("groq path failed user=%s", uid)
        await update.message.reply_text(
            "Is request ka answer abhi complete nahi ho paaya. Thodi der baad try karo."
        )
        return None
    except Exception:
        logger.exception("groq path failed user=%s", uid)
        await update.message.reply_text(
            "AI response generate nahi ho paaya. Thodi der mein dobara try karo."
        )
        return None
