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
):
    """Build a simple chat chain (no tools / no agent).
    Pure conversation follows the system prompt much more reliably.
    """
    system = SYSTEM_PROMPT.format(
        current_mood=current_mood or "Horny / Flirty",
        user_profile=profile_to_prompt_text(user_profile),
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    # Simple chain — no AgentExecutor, no scratchpad, no tool-calling format
    chain = prompt | llm | StrOutputParser()
    return chain
