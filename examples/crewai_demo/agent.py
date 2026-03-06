"""
CrewAI + ECP Integration Example
=================================
This example is taken from the CrewAI official documentation patterns:
  - Agent with a custom @tool (docs.crewai.com/concepts/tools)
  - Task with description + expected_output (docs.crewai.com/concepts/tasks)
  - Crew with sequential process (docs.crewai.com/concepts/crews)

It wraps the Crew using the ECP CrewAI Adapter so the ECP Runtime
can orchestrate, grade, and report on the agent's behavior.
"""

import os
from dotenv import load_dotenv

# Load .env so OPENAI_API_KEY is available
load_dotenv()

from crewai import Agent, Crew, Process, Task
from crewai.tools import tool

from ecp import serve
from ecp.adaptors.crewai import ECPCrewAIAdapter


# ---------------------------------------------------------------------------
# 1. Tools  (Following CrewAI docs: @tool decorator pattern)
# ---------------------------------------------------------------------------

@tool("calculator")
def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression. Supports +, -, *, / and parentheses."""
    allowed = set("0123456789+-*/() .")
    if not expression or any(ch not in allowed for ch in expression):
        return "Invalid expression."
    try:
        result = eval(expression, {"__builtins__": {}})
        # Return integer if the result is a whole number
        if isinstance(result, float) and result == int(result):
            return str(int(result))
        return str(result)
    except Exception:
        return "Invalid expression."


@tool("word_counter")
def word_counter(text: str) -> str:
    """Count the number of words in the given text."""
    if not text:
        return "0"
    return str(len(text.split()))


# ---------------------------------------------------------------------------
# 2. Agent  (Following CrewAI docs: Direct Code Definition)
# ---------------------------------------------------------------------------

math_agent = Agent(
    role="Math Specialist",
    goal="Solve arithmetic and word problems accurately using tools when needed",
    backstory=(
        "You are a careful mathematician who always verifies calculations "
        "with the calculator tool. You never do mental math — you always "
        "use the calculator tool to ensure accuracy."
    ),
    tools=[calculator, word_counter],
    verbose=False,
    allow_delegation=False,
)


# ---------------------------------------------------------------------------
# 3. Task  (Following CrewAI docs: Direct Code Definition)
# ---------------------------------------------------------------------------

solve_task = Task(
    description=(
        "Solve this problem: {input}. "
        "You MUST use the calculator tool for any arithmetic. "
        "Provide a concise final answer with the numeric result."
    ),
    expected_output="A concise answer that includes the final numeric result.",
    agent=math_agent,
)


# ---------------------------------------------------------------------------
# 4. Crew  (Following CrewAI docs: Sequential Process)
# ---------------------------------------------------------------------------

crew = Crew(
    agents=[math_agent],
    tasks=[solve_task],
    process=Process.sequential,
    verbose=False,
)


# ---------------------------------------------------------------------------
# 5. ECP Adapter  (Wire CrewAI into the ECP protocol)
# ---------------------------------------------------------------------------

def _to_inputs(input_text: str):
    """Maps ECP step input string to CrewAI kickoff inputs dict."""
    return {"input": input_text}


ecp_agent = ECPCrewAIAdapter(crew, name="CrewMathBot", input_mapper=_to_inputs)


# ---------------------------------------------------------------------------
# 6. Serve  (Start the ECP JSON-RPC server on stdio)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    serve(ecp_agent)
