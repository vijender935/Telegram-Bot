from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor

from bot.agent.prompts import SYSTEM_PROMPT
from bot.domain.learning import profile_to_prompt_text


def build_chat_agent(
    llm: ChatGroq,
    tools: list,
    current_mood: str,
    user_profile: dict | None = None,
) -> AgentExecutor:
    system = SYSTEM_PROMPT.format(
        current_mood=current_mood or "Horny / Flirty",
        user_profile=profile_to_prompt_text(user_profile),
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=3,
        max_execution_time=20,
    )
