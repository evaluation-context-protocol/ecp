import os
from dotenv import load_dotenv

# Load .env so OPENAI_API_KEY is available
load_dotenv()

from pydantic_ai import Agent, RunContext
from ecp import serve
from ecp.adaptors.pydantic_ai import ECPPydanticAIAdapter

# ---------------------------------------------------------------------------
# 1. Tools (PydanticAI pattern)
# ---------------------------------------------------------------------------

def calculator(ctx: RunContext[None], expression: str) -> str:
    """Evaluate a simple arithmetic expression. Supports +, -, *, / and parentheses."""
    allowed = set("0123456789+-*/() .")
    if not expression or any(ch not in allowed for ch in expression):
        return "Invalid expression."
    try:
        # Note: eval is used for simplicity in this demo.
        result = eval(expression, {"__builtins__": {}})
        if isinstance(result, float) and result == int(result):
            return str(int(result))
        return str(result)
    except Exception:
        return "Invalid expression."


# ---------------------------------------------------------------------------
# 2. PydanticAI Agent
# ---------------------------------------------------------------------------

# We use gpt-4o as it's a standard reliable model.
# In PydanticAI, tools are registered using decorators or the tools argument.
math_agent = Agent(
    'openai:gpt-4o',
    system_prompt=(
        "You are a helpful math assistant. "
        "Use the calculator tool for all arithmetic operations. "
        "Always show your reasoning before giving the final answer."
    )
)

# Register the tool
math_agent.tool(calculator)


# ---------------------------------------------------------------------------
# 3. ECP Adapter
# ---------------------------------------------------------------------------

ecp_agent = ECPPydanticAIAdapter(math_agent, name="PydanticAIMathBot")


# ---------------------------------------------------------------------------
# 4. Serve
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    serve(ecp_agent)
