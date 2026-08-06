from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from bot.agent.prompts import SYSTEM_PROMPT
from bot.domain.learning import profile_to_prompt_text


def build_chat_agent(
    llm: ChatGroq,
    tools: list,
    current_mood: str,
    user_profile: dict | None = None,
    session_summary: str = "",
    last_media: str = "",
    active_fantasy: str = "",
    emotion: str = "neutral",
    time_context: str = "Night time vibe.",
):
    """Simple chat chain with rich context injection."""
    # Inject personality evolution
    evolution_text = ""
    if user_profile and user_profile.get("persona_evolution"):
        evolution_text = "\n## Personality Evolution\n" + "\n".join([f"- {e}" for e in user_profile["persona_evolution"]])

    system = SYSTEM_PROMPT.format(
        current_mood=current_mood or "Horny / Flirty",
        user_profile=profile_to_prompt_text(user_profile),
        session_summary=session_summary or "(no session summary yet)",
        last_media=last_media or "(no recent media shared)",
        active_fantasy=active_fantasy or "(none)",
        emotion=emotion or "neutral",
        time_context=time_context,
    ) + evolution_text
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    chain = prompt | llm | StrOutputParser()
    return chain
