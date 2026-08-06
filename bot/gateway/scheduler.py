import logging
import random
from telegram.ext import ContextTypes
from bot.gateway.base import _allowed
from bot.domain.orchestrator import build_context_packet
from bot.domain.learning import profile_to_prompt_text
from bot.agent.prompts import SYSTEM_PROMPT
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

async def proactive_ping(context: ContextTypes.DEFAULT_TYPE):
    """Send a contextual, AI-generated message to allowed users periodically."""
    memory = context.application.bot_data["memory"]
    llm = context.application.bot_data["llm"]
    
    uids = memory.get_all_user_ids()
    if not uids:
        return

    for uid in uids:
        if not _allowed(uid):
            continue
        
        # 1 in 5 chance to actually ping
        if random.random() > 0.2:
            continue
            
        try:
            ctx = build_context_packet(memory, uid)
            history = memory.get_history(uid)
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT.format(
                    current_mood=ctx["mood"],
                    user_profile=profile_to_prompt_text(ctx["profile"]),
                    session_summary=ctx["session_summary_text"],
                    last_media=ctx["last_media_text"],
                    active_fantasy=ctx["fantasy_text"],
                    emotion=ctx["emotion"],
                    time_context=ctx["time_context"],
                ) + "\n\n## Task\nGenerate a short, addictive, and very personal proactive message to start a conversation. Use the current mood and profile. Don't use any tags."),
                MessagesPlaceholder("chat_history"),
                ("human", "Say something to me..."),
            ])
            chain = prompt | llm | StrOutputParser()
            msg = await chain.ainvoke({"chat_history": history[-5:]})
            
            if msg:
                await context.bot.send_message(chat_id=uid, text=msg)
                logger.info("Sent AI proactive ping to %s", uid)
        except Exception:
            logger.exception("AI Proactive ping failed for %s", uid)
