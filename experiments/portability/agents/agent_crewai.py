"""The refund desk as a single CrewAI agent."""

import core
from crewai import LLM, Agent, Crew, Process, Task
from crewai.tools import tool
from ecp.adaptors.crewai import ECPCrewAIAdapter

tools = [
    tool("lookup_order")(core.lookup_order),
    tool("check_refund_policy")(core.check_refund_policy),
    tool("issue_refund")(core.issue_refund),
]

agent = Agent(
    role="Refund Support Agent",
    goal="Answer the customer's refund question accurately",
    backstory=core.SYSTEM_PROMPT,
    tools=tools,
    llm=LLM(model=f"anthropic/{core.MODEL}", max_tokens=1024),
    allow_delegation=False,
    verbose=False,
)
task = Task(
    description="{customer_request}",
    expected_output="A two or three sentence reply to the customer.",
    agent=agent,
)
crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

adapter = ECPCrewAIAdapter(crew, name="RefundDesk-CrewAI", input_mapper=lambda t: {"customer_request": t})

if __name__ == "__main__":
    core.finish(adapter)
