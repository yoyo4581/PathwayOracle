from typing import Any, List, Tuple

from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from langchain.schema import AIMessage, HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_function

from AgentFiles.FunctionTool import FunctionTool
from AgentFiles.OntoTool import CommonGeneTool
from AgentFiles.PubFindTool import PubInfoLinkedTool
import os

from db import chat_llm



tools = [FunctionTool(), CommonGeneTool(), PubInfoLinkedTool()]

# converts AgentAction tool output tuples into FunctionMessages.
llm_with_tools = chat_llm.bind(functions=[convert_to_openai_function(t) for t in tools])

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant that finds information about genes and their interactions. "
            "Use only tools to provide answers."
            "Use only the most relevant pieces of information before outputting the answer. "
            "Provide concise and clear responses, summarizing information by emphasizing the outcome rather than the methods. "
            "Do only the things the user specifically requested. "
            "Structure your responses in a clear and organized manner, using bullet points or lists when appropriate."
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)


def _format_chat_history(chat_history: List[Tuple[str, str]]):
    buffer = []
    for human, ai in chat_history:
        buffer.append(HumanMessage(content=human))
        buffer.append(AIMessage(content=ai))
    return buffer


agent = (
    {
        "input": lambda x: x["input"],
        "chat_history": lambda x: _format_chat_history(x["chat_history"])
        if x.get("chat_history")
        else [],
        "agent_scratchpad": lambda x: format_to_openai_function_messages(
            x["intermediate_steps"]
        ),
    }
    | prompt
    | llm_with_tools
    | OpenAIFunctionsAgentOutputParser()
)


# Add typing for input
class AgentInput(BaseModel):
    input: str
    chat_history: List[Tuple[str, str]] = Field(
        ..., extra={"widget": {"type": "chat", "input": "input", "output": "output"}}
    )


class Output(BaseModel):
    output: Any


# Ensure the agent_executor is correctly instantiated
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True).with_types(
    input_type=AgentInput, output_type=Output
)