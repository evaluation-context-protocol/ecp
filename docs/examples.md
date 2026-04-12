# Examples

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Docs Home](https://evaluationcontextprotocol.io/)

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
from crewai import Agent, Crew, Process, Task
from crewai.tools import tool

from ecp import serve
from ecp.adaptors.crewai import ECPCrewAIAdapter


@tool("calculator")
def calculator(expression: str) -> str:
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

crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)

ecp_agent = ECPCrewAIAdapter(crew, name="CrewMathBot")

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
load_dotenv()
from pydantic_ai import Agent, RunContext
from ecp import serve
from ecp.adaptors.pydantic_ai import ECPPydanticAIAdapter

def calculator(ctx: RunContext[None], expression: str) -> str:
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

math_agent = Agent(
    'openai:gpt-4o',
    system_prompt=(
        "You are a helpful math assistant. "
        "Use the calculator tool for all arithmetic operations. "
        "Always show your reasoning before giving the final answer."
    )
)
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
