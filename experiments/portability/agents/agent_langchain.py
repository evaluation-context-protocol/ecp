"""The refund desk as a LangChain agent."""

import core
from ecp.adaptors.langchain import ECPLangChainAdapter
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

tools = [tool(core.lookup_order), tool(core.check_refund_policy), tool(core.issue_refund)]

llm = ChatAnthropic(model=core.MODEL, max_tokens=1024)
graph = create_agent(llm, tools, system_prompt=core.SYSTEM_PROMPT)

adapter = ECPLangChainAdapter(
    graph,
    name="RefundDesk-LangChain",
    input_mapper=lambda text: {"messages": [("user", text)]},
)

if __name__ == "__main__":
    core.finish(adapter)
