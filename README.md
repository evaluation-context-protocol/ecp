# Evaluation Context Protocol (ECP)

![Status](https://img.shields.io/badge/Status-Experimental-orange)
![License](https://img.shields.io/badge/License-Apache%202.0-blue)

**Portable evaluations for AI agents.**

ECP is a vendor-neutral protocol and reference runtime for testing agent outputs, tool calls, and evaluator-visible audit context across frameworks, models, eval platforms, and CI systems.

MCP gives agents a common way to use tools. ECP gives evaluators a common way to inspect what an agent returned, what tools it used, and what audit evidence it exposed.

> Status: experimental but usable. The current package line is `0.3.1`.

## Why ECP

Most eval tools are useful, but they often couple the evaluation contract to a specific SDK, trace model, dashboard, or hosted workflow. ECP separates the contract from the platform.

Use ECP when you want to:

- run repeatable agent evals locally or in CI
- verify final answers and required tool usage
- expose evaluator-safe `evaluation_context` without relying on raw chain-of-thought
- keep reports portable as JSON or HTML
- integrate plain Python, LangChain, LlamaIndex, CrewAI, PydanticAI, or your own runtime

## Quick Start

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install "ecp-runtime==0.3.1" "ecp-sdk==0.3.1"
ecp init
ecp validate ecp_eval/manifest.yaml
ecp run --manifest ecp_eval/manifest.yaml --json
```

Run the flagship policy/tool-use demo:

```bash
ecp run --manifest examples/customer_support_demo/manifest.yaml --report report.html
```

## ECP In 60 Seconds

ECP is JSON-RPC 2.0 over stdio or Streamable HTTP. The runtime calls:

- `agent/initialize`
- `agent/step`
- `agent/reset`

The agent returns:

- `public_output` - user-visible answer
- `evaluation_context` - evaluator-safe audit evidence
- `tool_calls` - actions the agent took

`private_thought` is still accepted as a deprecated compatibility alias for `evaluation_context`.

## Example Result

```python
from ecp import Result, agent, on_step, serve


@agent(name="SupportAgent")
class SupportAgent:
    @on_step
    def step(self, user_input: str):
        return Result(
            public_output="Order A100 is eligible for a refund.",
            evaluation_context="Checked order A100 and confirmed it is inside the 30-day refund window.",
            tool_calls=[
                {"name": "lookup_order", "arguments": {"order_id": "A100"}},
                {"name": "check_refund_policy", "arguments": {"order_id": "A100"}},
            ],
        )


if __name__ == "__main__":
    serve(SupportAgent())
```

## CLI

```bash
ecp init
ecp validate examples/customer_support_demo/manifest.yaml
ecp run --manifest examples/customer_support_demo/manifest.yaml --json
ecp run --manifest examples/customer_support_demo/manifest.yaml --json-out report.json
ecp run --manifest examples/customer_support_demo/manifest.yaml --report report.html
ecp conformance --target "python examples/customer_support_demo/agent.py"
ecp doctor
```

## Repo Layout

- `sdk/` - Python SDK for implementing ECP agents
- `runtime/` - Python runtime and `ecp` CLI
- `examples/customer_support_demo` - realistic flagship demo
- `examples/` - framework demos
- `schema/` - JSON Schema contracts
- `client/` and `server/` - local ECP Inspector UI and proxy server
- `spec/` and `docs/spec.md` - protocol specification

## Documentation

- Docs site: https://evaluationcontextprotocol.io/
- Quickstart: https://evaluationcontextprotocol.io/quickstart/
- Specification: https://evaluationcontextprotocol.io/spec/

