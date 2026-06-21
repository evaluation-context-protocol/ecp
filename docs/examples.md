# Examples

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Docs Home](https://evaluationcontextprotocol.io/)

## Customer Support Policy Example

Agent file: `examples/customer_support_demo/agent.py`

This is the flagship example. It shows why ECP is more than an output checker: the manifest verifies the final answer, the required order lookup, the refund policy check, and the evaluator-safe `evaluation_context`.

Run it:

```bash
ecp run --manifest examples/customer_support_demo/manifest.yaml --report report.html
```

### Customer Support Manifest

```yaml
manifest_version: "v1"
name: "Customer Support Refund Policy"
target: "python examples/customer_support_demo/agent.py"

scenarios:
  - name: "Eligible refund uses order lookup and policy check"
    steps:
      - input: "I want a refund for order A100."
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "eligible for a refund"
          - type: text_match
            field: evaluation_context
            condition: contains
            value: "refund_eligible=True"
          - type: tool_usage
            tool_name: "lookup_order"
            arguments:
              order_id: "A100"
```

## Plain Python App Example

Agent file: `examples/plain_python_demo/agent.py`

This example uses only the ECP SDK. It does not depend on any external agent framework.

### Plain Python Manifest

```yaml
manifest_version: "v1"
name: "Plain Python App Validation"
target: "python examples/plain_python_demo/agent.py"

scenarios:
  - name: "Arithmetic Request"
    steps:
      - input: "calc: (18 + 6) * 3"
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "72"

          - type: tool_usage
            tool_name: "calculator"
            arguments:
              expression: "(18 + 6) * 3"
```

## Two-Agent Workflow Example

Agent file: `examples/two_agent_demo/agent.py`

This example shows a small planner/writer workflow wrapped behind a single ECP server.

### Two-Agent Manifest

```yaml
manifest_version: "v1"
name: "Two-Agent Workflow Validation"
target: "python examples/two_agent_demo/agent.py"

scenarios:
  - name: "Launch Note Drafting"
    steps:
      - input: "the ECP beta launch"
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "the latest validation is green"

          - type: tool_usage
            tool_name: "planner_agent"
            arguments:
              request: "the ECP beta launch"

          - type: tool_usage
            tool_name: "writer_agent"
            arguments:
              request: "the ECP beta launch"
```

## Streamable HTTP Transport Example

Agent file: `examples/streamable_http_demo/agent.py`

Start the agent service first:

```bash
python examples/streamable_http_demo/agent.py
```

Then run the manifest from another terminal:

```bash
ecp run --manifest examples/streamable_http_demo/manifest.yaml --json
```

### Streamable HTTP Manifest

```yaml
manifest_version: "v1"
name: "Streamable HTTP Transport Validation"
target: "http://127.0.0.1:8765/ecp"

scenarios:
  - name: "HTTP Echo"
    steps:
      - input: "echo: transport is online"
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "transport is online"

          - type: tool_usage
            tool_name: "http_echo"
            arguments:
              message: "transport is online"
```

## Async Python Agent Example

Agent file: `examples/async_python_demo/agent.py`

This example uses `async def` for both `@on_step` and `@on_reset`. The SDK awaits both hooks on a persistent event loop, allowing async clients to be reused safely between requests.

Run it over stdio:

```bash
ecp run --manifest examples/async_python_demo/manifest.yaml --timeout 10
```

Or start the same agent over Streamable HTTP:

```bash
ECP_TRANSPORT=http ECP_HTTP_PORT=8765 python examples/async_python_demo/agent.py
ecp conformance --target http://127.0.0.1:8765/ecp --timeout 10
```

## LangChain Example

Agent file: `examples/langchain_demo/agent.py`

### LangChain Manifest (Full Scenarios)

```yaml
manifest_version: "v1"
name: "LangChain Math Check"
target: "python agent.py"

scenarios:
  - name: "Ratio Word Problem"
    steps:
      - input: "Katy makes coffee using teaspoons of sugar and cups of water in the ratio of 7:13. If she used a total of 120 teaspoons of sugar and cups of water, calculate the number of teaspoonfuls of sugar she used."
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "42"

          - type: llm_judge
            field: public_output
            prompt: "Does the response state the correct final number and clearly indicate it refers to the amount of sugar?"

          - type: tool_usage
            tool_name: "calculator"
            arguments: {}

  - name: "Weekly Letters"
    steps:
      - input: "James writes a 3-page letter to 2 different friends twice a week. How many pages does he write a year?"
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "624"

          - type: llm_judge
            field: public_output
            prompt: "Does the response state the correct final number and clearly indicate it refers to pages written per year?"

          - type: tool_usage
            tool_name: "calculator"
            arguments: {}
```

## LlamaIndex Example

Agent file: `examples/llamaindex_demo/agent.py`

```python
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI
from llama_index.tools.yahoo_finance import YahooFinanceToolSpec

from ecp import serve
from ecp.adaptors.llama_index import ECPLlamaIndexAdapter


def multiply(a: float, b: float) -> float:
    return a * b


def add(a: float, b: float) -> float:
    return a + b


finance_tools = YahooFinanceToolSpec().to_tool_list()
finance_tools.extend([multiply, add])

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
```

## CrewAI Example

Agent file: `examples/crewai_demo/agent.py`

```python
import os
from dotenv import load_dotenv

# Load .env so OPENAI_API_KEY is available
load_dotenv()

from crewai import Agent, Crew, Process, Task
from crewai.tools import tool

from ecp import serve
from ecp.adaptors.crewai import ECPCrewAIAdapter


@tool("calculator")
def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression. Supports +, -, *, / and parentheses."""
    allowed = set("0123456789+-*/() .")
    if not expression or any(ch not in allowed for ch in expression):
        return "Invalid expression."
    try:
        result = eval(expression, {"__builtins__": {}})
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

solve_task = Task(
    description=(
        "Solve this problem: {input}. "
        "You MUST use the calculator tool for any arithmetic. "
        "Provide a concise final answer with the numeric result."
    ),
    expected_output="A concise answer that includes the final numeric result.",
    agent=math_agent,
)

crew = Crew(
    agents=[math_agent],
    tasks=[solve_task],
    process=Process.sequential,
    verbose=False,
)

def _to_inputs(input_text: str):
    """Maps ECP step input string to CrewAI kickoff inputs dict."""
    return {"input": input_text}

ecp_agent = ECPCrewAIAdapter(crew, name="CrewMathBot", input_mapper=_to_inputs)

if __name__ == "__main__":
    serve(ecp_agent)
```

### CrewAI Manifest

```yaml
manifest_version: "v1"
name: "CrewAI Docs Integration Test"
target: "python agent.py"

scenarios:
  - name: "Simple Arithmetic"
    steps:
      - input: "What is 15 multiplied by 8?"
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "120"

          - type: tool_usage
            tool_name: "calculator"
            arguments: {}

  - name: "Ratio Word Problem"
    steps:
      - input: "Katy makes coffee using teaspoons of sugar and cups of water in the ratio of 7:13. If she used a total of 120 teaspoons of sugar and cups of water, calculate the number of teaspoonfuls of sugar she used."
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "42"

          - type: tool_usage
            tool_name: "calculator"
            arguments: {}

  - name: "Multi-Step Calculation"
    steps:
      - input: "James writes a 3-page letter to each of 2 different friends, and he does this 2 times every week. How many total pages does he write in a year (52 weeks)?"
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "624"

          - type: tool_usage
            tool_name: "calculator"
            arguments: {}
```

## Pydantic AI Example

Agent file: `examples/pydantic_ai_demo/agent.py`

```python
import os
from dotenv import load_dotenv

# Load .env so OPENAI_API_KEY is available
load_dotenv()

from pydantic_ai import Agent, RunContext
from ecp import serve
from ecp.adaptors.pydantic_ai import ECPPydanticAIAdapter

def calculator(ctx: RunContext[None], expression: str) -> str:
    """Evaluate a simple arithmetic expression. Supports +, -, *, / and parentheses."""
    allowed = set("0123456789+-*/() .")
    if not expression or any(ch not in allowed for ch in expression):
        return "Invalid expression."
    try:
        result = eval(expression, {"__builtins__": {}})
        if isinstance(result, float) and result == int(result):
            return str(int(result))
        return str(result)
    except Exception:
        return "Invalid expression."

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

ecp_agent = ECPPydanticAIAdapter(math_agent, name="PydanticAIMathBot")

if __name__ == "__main__":
    serve(ecp_agent)
```

### Pydantic AI Manifest

```yaml
manifest_version: "v1"
name: "PydanticAI Integration Test"
target: "python agent.py"

scenarios:
  - name: "Basic Math"
    steps:
      - input: "What is 123 * 456?"
        graders:
          - type: text_match
            field: public_output
            condition: regex
            pattern: "56,?088"
          - type: tool_usage
            tool_name: "calculator"
            arguments: {}

  - name: "Word Problem"
    steps:
      - input: "If I have 15 Apples and I give 7 to my friend, how many do I have left?"
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "8"
          - type: tool_usage
            tool_name: "calculator"
            arguments: {}
```
