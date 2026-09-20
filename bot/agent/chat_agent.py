"""Conversation chain construction."""
from __future__ import annotations

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from bot import config
from bot.agent.prompts import SYSTEM_PROMPT
from bot.domain.learning import profile_to_prompt_text


def build_chat_agent_with_components(
    llm: ChatGroq,
    tools: list,
    current_mood: str,
    user_profile: dict | None = None,
    session_summary: str = "",
    last_media: str = "",
    active_fantasy: str = "",
    emotion: str = "neutral",
    time_context: str = "",
    memory_context: str = "",
    response_policy: str = "mode=conversation; language=hinglish; length=adaptive; ask_followup=False; explain=False",
):
    """Build the conversational model with explicit policy and relevance-ranked context."""
    evolution_text = ""
    if user_profile and user_profile.get("persona_evolution"):
        evolution_text = "\n## Learned style adjustments\n" + "\n".join(
            f"- {e}" for e in user_profile["persona_evolution"]
        )

    system = SYSTEM_PROMPT.format(
        current_mood=current_mood or "neutral",
        user_profile=profile_to_prompt_text(user_profile),
        session_summary=session_summary or "(no session summary yet)",
        last_media=last_media or "(no recent media shared)",
        active_fantasy=active_fantasy or "(none)",
        emotion=emotion or "neutral",
        time_context=time_context or "current time context unavailable",
        memory_context=memory_context or "(no relevant long-term memories)",
        response_policy=response_policy,
    ) + evolution_text

    # System content contains user/profile/memory text. Passing it as a
    # SystemMessage prevents literal braces in that data (for example JSON)
    # from being interpreted as LangChain template variables.
    system_message = SystemMessage(content=system)
    prompt = ChatPromptTemplate.from_messages([
        system_message,
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    model = llm.bind_tools(tools) if tools else llm
    return prompt | model, system_message, model


def build_chat_agent(
    llm: ChatGroq,
    tools: list,
    current_mood: str,
    user_profile: dict | None = None,
    session_summary: str = "",
    last_media: str = "",
    active_fantasy: str = "",
    emotion: str = "neutral",
    time_context: str = "",
    memory_context: str = "",
    response_policy: str = "mode=conversation; language=hinglish; length=adaptive; ask_followup=False; explain=False",
):
    """Build the conversational model with explicit policy and relevance-ranked context."""
    return build_chat_agent_with_components(
        llm, tools, current_mood, user_profile, session_summary, last_media,
        active_fantasy, emotion, time_context, memory_context, response_policy,
    )[0]


def build_llm(model_name: str | None = None) -> ChatGroq:
    """Create the Groq client with an explicit completion budget.

    Groq's on-demand tier enforces a tokens-per-minute request budget. Keeping
    the completion cap bounded prevents a valid conversation context from
    becoming a 413 when the default model output budget is too large.
    """
    return ChatGroq(
        model=model_name or config.GROQ_MODEL,
        groq_api_key=config.GROQ_API_KEY,
        temperature=config.TEMPERATURE,
        max_tokens=config.GROQ_MAX_TOKENS,
    )
