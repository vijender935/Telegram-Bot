"""Optional proactive Telegram scheduler using the current context model.

The scheduler is intentionally lightweight and uses only fields produced by
build_context_packet(). It does not depend on removed mood/fantasy/emotion
systems.
"""
from __future__ import annotations

import logging
import random

from telegram.ext import ContextTypes
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from bot.agent.prompts import CHAT_SYSTEM_PROMPT
from bot.domain.learning import profile_to_prompt_text
from bot.domain.orchestrator import build_context_packet

logger = logging.getLogger(__name__)


async def proactive_ping(context: ContextTypes.DEFAULT_TYPE):
    """Occasionally send a short contextual message to existing users."""
    memory = context.application.bot_data["memory"]
    llm = context.application.bot_data["llm"]

    user_ids = memory.get_all_user_ids()
    if not user_ids:
        return

    for user_id in user_ids:
        if random.random() > 0.2:
            continue

        try:
            ctx = build_context_packet(memory, user_id, "proactive conversation starter")
            history = memory.get_history(user_id)

            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        CHAT_SYSTEM_PROMPT
                        + "\n\n## Task\n"
                        "Generate one short, natural proactive message to start a conversation. "
                        "Use the supplied context only when relevant. Do not mention internal context or tags.",
                    ),
                    MessagesPlaceholder("chat_history"),
                    ("human", "Say something to start a conversation."),
                ]
            )
            chain = prompt | llm | StrOutputParser()
            msg = await chain.ainvoke(
                {
                    "time_context": ctx["time_context"],
                    "user_profile": profile_to_prompt_text(ctx["profile"]),
                    "session_summary": ctx["session_summary_text"],
                    "memory_context": ctx["memory_context_text"],
                    "last_media": ctx["last_media_text"],
                    "chat_history": history[-5:],
                }
            )

            if msg:
                await context.bot.send_message(chat_id=user_id, text=msg.strip())
                logger.info("Sent proactive ping to %s", user_id)
        except Exception:
            logger.exception("Proactive ping failed for %s", user_id)
