from crewai import Agent, Crew, Process, Task
from crewai.tools import tool

from ecp import serve
from ecp.adaptors.crewai import ECPCrewAIAdapter


@tool("calculator")
def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression."""
    allowed = set("0123456789+-*/() ")
    if not expression or any(ch not in allowed for ch in expression):
        return "Invalid expression."
    try:
        return str(int(eval(expression, {"__builtins__": {}})))
    except Exception:
        return "Invalid expression."


agent = Agent(
    role="Math Specialist",
    goal="Solve arithmetic accurately using tools when needed",
    backstory="You are careful with arithmetic and verify calculations with tools.",
    tools=[calculator],
    verbose=True,
    allow_delegation=False,
)

task = Task(
    description=(
        "Solve this math problem: {input}. "
        "Use the calculator tool for arithmetic and provide a concise final answer."
    ),
    expected_output="A concise answer that includes the final numeric result.",
    agent=agent,
)

crew = Crew(
    agents=[agent],
    tasks=[task],
    process=Process.sequential,
    verbose=True,
)


def _to_inputs(input_text: str):
    return {"input": input_text}


ecp_agent = ECPCrewAIAdapter(crew, name="CrewMathBot", input_mapper=_to_inputs)

if __name__ == "__main__":
    serve(ecp_agent)
