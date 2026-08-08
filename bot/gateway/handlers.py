import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage, AIMessage

from bot import config
from bot.gateway.base import _allowed
from bot.gateway.formatters import send_long_text
from bot.domain.orchestrator import build_context_packet, maybe_update_session_summary
from bot.domain.learning import should_extract, extract_and_merge
from bot.agent.chat_agent import build_chat_agent

# Import other handlers
from bot.gateway.commands import *
from bot.gateway.media import *
from bot.gateway.vault import *
from bot.gateway.scheduler import proactive_ping

logger = logging.getLogger(__name__)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    
    uid = update.effective_user.id
    user_text = update.message.text
    memory = context.application.bot_data["memory"]
    llm = context.application.bot_data["llm"]
    tools = context.application.bot_data["tools"]

    # 1. Context & History
    ctx = build_context_packet(memory, uid, user_text=user_text)
    history = memory.get_history(uid)
    history.append(HumanMessage(content=user_text))
    memory.save_history(uid, history, config.MAX_HISTORY_MESSAGES)

    # 2. Agent Invoke
    try:
        chain = build_chat_agent(
            llm, tools,
            current_mood=ctx["mood"],
            user_profile=ctx["profile"],
            session_summary=ctx["session_summary_text"],
            last_media=ctx["last_media_text"],
            active_fantasy=ctx["fantasy_text"],
            emotion=ctx["emotion"],
            time_context=ctx["time_context"],
        )
        
        full_reply = await chain.ainvoke({"input": user_text, "chat_history": history[:-1]})
        
        # 3. Action Tag Processing
        clean_reply = full_reply
        actions = []
        
        # Regex to find tags like [VOICE], [VAULT_ADD], [DRIVE_GET: query]
        tag_pattern = r"\[([A-Z_]+)(?::\s*([^\]]+))?\]"
        matches = list(re.finditer(tag_pattern, full_reply))
        
        for match in matches:
            tag = match.group(1)
            val = match.group(2)
            actions.append((tag, val))
            clean_reply = clean_reply.replace(match.group(0), "")
            
        clean_reply = clean_reply.strip()
        
        # 4. Save & Reply
        if clean_reply:
            history.append(AIMessage(content=clean_reply))
            memory.save_history(uid, history, config.MAX_HISTORY_MESSAGES)
            await send_long_text(update, clean_reply)
        
        # 5. Execute Actions
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
                    drive = context.application.bot_data.get("drive")
                    if drive and val:
                        await update.message.reply_text("Ruko, dhundh rahi hoon... 👁️")
                        status, msg = drive.download_semantic(uid, val, config.SANDBOX_PATH)
                        if status == "ok":
                            from bot.gateway.media import _send_media_with_followup
                            await _send_media_with_followup(update, context, msg, uid)
                        else:
                            await update.message.reply_text(msg)

                elif tag == "SET_EMOTION":
                    if val:
                        emotion_val = val.strip().lower()
                        memory.set_emotion(uid, emotion_val)
                        logger.info("Emotion set to %s for user %s", emotion_val, uid)

                elif tag == "EVOLVE":
                    if val:
                        profile = memory.get_profile(uid) or {}
                        evolutions = profile.get("persona_evolution", [])
                        evolutions.append(val.strip())
                        profile["persona_evolution"] = evolutions[-8:]  # keep last 8
                        memory.set_profile(uid, profile)
                        logger.info("Personality evolved: %s", val)

            except Exception:
                logger.exception(f"Action {tag} failed")

        # 6. Learning & Summary (Background)
        if should_extract(user_text, clean_reply):
            new_info = await extract_and_merge(llm, user_text, clean_reply, ctx["profile"])
            memory.set_profile(uid, new_info)

        await maybe_update_session_summary(llm, memory, uid, user_text, clean_reply)

    except Exception:
        logger.exception("Chat failed")
        await update.message.reply_text("Abhi dimaag kaam nahi kar raha, thodi der mein baat karte hain? 😈")
