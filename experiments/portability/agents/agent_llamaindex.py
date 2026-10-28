"""The refund desk as a LlamaIndex FunctionAgent."""

import core
from ecp.adaptors.llama_index import ECPLlamaIndexAdapter
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.anthropic import Anthropic

tools = [
    FunctionTool.from_defaults(fn=core.lookup_order),
    FunctionTool.from_defaults(fn=core.check_refund_policy),
    FunctionTool.from_defaults(fn=core.issue_refund),
]

llm = Anthropic(model=core.MODEL, max_tokens=1024)
agent = FunctionAgent(tools=tools, llm=llm, system_prompt=core.SYSTEM_PROMPT)

adapter = ECPLlamaIndexAdapter(agent, name="RefundDesk-LlamaIndex")

if __name__ == "__main__":
    core.finish(adapter)
