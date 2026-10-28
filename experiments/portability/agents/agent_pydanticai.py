"""The refund desk as a PydanticAI agent."""

import core
from ecp.adaptors.pydantic_ai import ECPPydanticAIAdapter
from pydantic_ai import Agent

agent = Agent(
    f"anthropic:{core.MODEL}",
    system_prompt=core.SYSTEM_PROMPT,
    tools=[core.lookup_order, core.check_refund_policy, core.issue_refund],
)

adapter = ECPPydanticAIAdapter(agent, name="RefundDesk-PydanticAI")

if __name__ == "__main__":
    core.finish(adapter)
