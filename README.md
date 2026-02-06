# Evaluation Context Protocol (ECP)

![Status](https://img.shields.io/badge/Status-Experimental-orange)
![License](https://img.shields.io/badge/License-Apache%202.0-blue)


A lightweight protocol and reference runtime for evaluating agents with public output, private reasoning, and tool usage. This repo contains:

- `sdk/` - Python SDK for implementing an ECP agent.
- `runtime/` - Python runtime (CLI) that runs manifests and grades results.
- `examples/` - Minimal examples (LangChain demo).
- `spec/` - Protocol specification.


## Quick Start (Local Dev)

Create a venv and install runtime + SDK in editable mode:

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .\runtime\python
pip install -e .\sdk\python
```

Run the example manifest:

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml
```

Generate an HTML report:

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml --report .\report.html
```

Print a JSON report (useful for CI tooling):

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml --json
```

If your manifest uses `llm_judge`, set your key:

```bash
$env:OPENAI_API_KEY="your_key_here"
```

## Example (LangChain Agent + Manifest)

Agent (LangChain `create_agent` + tool usage):

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

Manifest (runtime checks output + tool usage):

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

## ECP in 60 Seconds

ECP is JSON-RPC 2.0 over stdio. The runtime launches your agent process and calls:

- `agent/initialize`
- `agent/step`
- `agent/reset`

Your agent replies with a structured result containing:

- `public_output` (what the user sees)
- `private_thought` (for evaluators)
- `tool_calls` (actions taken)

See `spec/protocol.md` for the full protocol.

## Repo Layout

- `sdk/python/src/ecp` - SDK decorators and server loop
- `runtime/python/src/ecp_runtime` - CLI, runner, graders
- `examples/langchain_demo` - LangChain-based demo agent and manifest

## Status

This project is evolving quickly. Expect changes between minor versions.
