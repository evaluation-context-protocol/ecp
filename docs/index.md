# Evaluation Context Protocol (ECP)

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [README](https://github.com/evaluation-context-protocol/ecp/blob/main/README.md)

ECP is a lightweight protocol and reference runtime for evaluating agents with public output, private reasoning, and tool usage.

It gives you a standard way to run deterministic evaluations without changing your production agent code.

## Why ECP exists

Most agent evaluations only check the final answer. That is not enough for safety or reliability.

Common gaps:

- Did the agent use the right tool or hallucinate data?
- Did it follow policy internally before responding?
- Did it reason correctly even if the final answer looks right?

ECP solves this by separating **public output** (what users see) from **private reasoning** and **tool calls** (what evaluators need to verify). The runtime can then grade each aspect explicitly.

## What you get

- A simple JSON-RPC protocol over stdio
- A reference runtime to execute manifests and graders
- Optional HTML report output for sharing results
- A Python SDK to wrap agents quickly
- Minimal examples to copy and modify

## Example (LangChain Agent + Manifest)

Agent:

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from ecp import serve
from ecp.adaptors.langchain import ECPLangChainAdapter

@tool
def calculator(expression: str) -> str:
    allowed = set("0123456789+-*/() ")
    if not expression or any(ch not in allowed for ch in expression):
        return "Invalid expression."
    try:
        return str(int(eval(expression, {"__builtins__": {}})))
    except Exception:
        return "Invalid expression."

agent = create_agent(
    model=ChatOpenAI(model="gpt-3.5-turbo", temperature=0),
    tools=[calculator],
    system_prompt="Use the calculator tool for arithmetic."
)

def to_messages(text: str):
    return {"messages": [{"role": "user", "content": text}]}

serve(ECPLangChainAdapter(agent, name="MathBot", input_mapper=to_messages))
```

Manifest:

```yaml
manifest_version: "v1"
name: "LangChain Math Check"
target: "python agent.py"

scenarios:
  - name: "Ratio Word Problem"
    steps:
      - input: "Katy makes coffee using teaspoons of sugar and cups of water in the ratio of 7:13..."
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "42"
          - type: tool_usage
            tool_name: "calculator"
            arguments: {}
```

## What is in this repo

- Python SDK: `sdk/python/src/ecp`
- Runtime CLI: `runtime/python/src/ecp_runtime`
- Examples: `examples/langchain_demo`
- Protocol spec: `spec/protocol.md`

Go to **Quickstart** to run the demo, or **Specification** to implement the protocol in another language.

