"""Conversation chain construction for Groq (tools) and Gemini (chat)."""
from __future__ import annotations

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from bot import config
from bot.agent.prompts import CHAT_SYSTEM_PROMPT, TOOL_SYSTEM_PROMPT
from bot.domain.learning import profile_to_prompt_text


def _format_chat_system(
    user_profile: dict | None = None,
    session_summary: str = "",
    last_media: str = "",
    time_context: str = "",
    memory_context: str = "",
) -> str:
    return CHAT_SYSTEM_PROMPT.format(
        user_profile=profile_to_prompt_text(user_profile),
        session_summary=session_summary or "(no session summary yet)",
        last_media=last_media or "(no recent media shared)",
        time_context=time_context or "current time context unavailable",
        memory_context=memory_context or "(no relevant long-term memories)",
    )


def _format_tool_system(
    user_profile: dict | None = None,
    session_summary: str = "",
    last_media: str = "",
    time_context: str = "",
    memory_context: str = "",
    response_policy: str = "mode=conversation; language=hinglish; length=adaptive; ask_followup=False; explain=False",
) -> str:
    return TOOL_SYSTEM_PROMPT.format(
        user_profile=profile_to_prompt_text(user_profile),
        session_summary=session_summary or "(no session summary yet)",
        last_media=last_media or "(no recent media shared)",
        time_context=time_context or "current time context unavailable",
        memory_context=memory_context or "(no relevant long-term memories)",
        response_policy=response_policy,
    )


def build_chat_agent_with_components(
    llm,
    tools: list,
    user_profile: dict | None = None,
    session_summary: str = "",
    last_media: str = "",
    time_context: str = "",
    memory_context: str = "",
    response_policy: str = "mode=conversation; language=hinglish; length=adaptive; ask_followup=False; explain=False",
    mode: str = "tools",
):
    """Build chain. mode='chat' uses Gemini identity prompt; mode='tools' uses Groq tool prompt."""
    if mode == "chat":
        system = _format_chat_system(
            user_profile, session_summary, last_media, time_context, memory_context
        )
    else:
        system = _format_tool_system(
            user_profile, session_summary, last_media, time_context, memory_context, response_policy
        )

    system_message = SystemMessage(content=system)
    prompt = ChatPromptTemplate.from_messages([
        system_message,
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    model = llm.bind_tools(tools) if tools else llm
    return prompt | model, system_message, model


def build_chat_agent(
    llm,
    tools: list,
    user_profile: dict | None = None,
    session_summary: str = "",
    last_media: str = "",
    time_context: str = "",
    memory_context: str = "",
    response_policy: str = "mode=conversation; language=hinglish; length=adaptive; ask_followup=False; explain=False",
    mode: str = "tools",
):
    return build_chat_agent_with_components(
        llm, tools, user_profile, session_summary, last_media,
        time_context, memory_context, response_policy, mode,
    )[0]


def build_groq_llm(model_name: str | None = None) -> ChatGroq:
    """Groq client for tool-calling path."""
    return ChatGroq(
        model=model_name or config.GROQ_MODEL,
        groq_api_key=config.GROQ_API_KEY,
        temperature=config.GROQ_TEMPERATURE,
        max_tokens=config.GROQ_MAX_TOKENS,
    )


def build_gemini_llm():
    """Gemini client for natural chat path. Requires langchain-google-genai."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        google_api_key=config.GEMINI_API_KEY,
        temperature=config.GEMINI_TEMPERATURE,
        max_output_tokens=config.GEMINI_MAX_TOKENS,
    )


# Backward-compatible alias used by main.py / media handlers
def build_llm(model_name: str | None = None):
    return build_groq_llm(model_name)
