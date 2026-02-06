import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../sdk/python/src')))

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from ecp import serve
from ecp.adaptors.langchain import ECPLangChainAdapter


@tool
def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression."""
    allowed = set("0123456789+-*/() ")
    if not expression or any(ch not in allowed for ch in expression):
        return "Invalid expression."
    try:
        return str(int(eval(expression, {"__builtins__": {}})))
    except Exception:
        return "Invalid expression."


agent = create_agent(
    model=ChatOpenAI(model="gpt-3.5-turbo", temperature=0),
    tools=[calculator],
    system_prompt="You are a helpful assistant. Use the calculator tool for arithmetic.",
)


def _to_messages(input_text: str):
    return {"messages": [{"role": "user", "content": input_text}]}


ecp_agent = ECPLangChainAdapter(agent, name="MathBot", input_mapper=_to_messages)

if __name__ == "__main__":
    serve(ecp_agent)
