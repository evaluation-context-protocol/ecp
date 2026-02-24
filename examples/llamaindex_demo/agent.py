from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI
from llama_index.tools.yahoo_finance import YahooFinanceToolSpec

from ecp import serve
from ecp.adaptors.llama_index import ECPLlamaIndexAdapter


def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


finance_tools = YahooFinanceToolSpec().to_tool_list()
finance_tools.extend([multiply, add])
# print(finance_tools)
workflow = FunctionAgent(
    name="Agent",
    description="Useful for performing financial operations.",
    llm=OpenAI(model="gpt-4o-mini"),
    tools=[multiply, add],
    system_prompt="You are a helpful assistant.",
)


ecp_agent = ECPLlamaIndexAdapter(workflow, name="FinanceBot")

if __name__ == "__main__":
    serve(ecp_agent)
