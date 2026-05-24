# Evaluation Context Protocol (ECP)

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Quickstart](quickstart.md) | [Specification](spec.md)

**Portable evaluations for AI agents.**

ECP is a vendor-neutral protocol for testing agent outputs, tool calls, and evaluator-visible audit context across frameworks, models, eval platforms, and CI systems.

Think of it as the evaluation contract layer: MCP gives agents a common way to use tools; ECP gives evaluators a common way to inspect what an agent returned, what tools it used, and what audit evidence it exposed.

## Why ECP Exists

Agent evaluations are still too tied to individual frameworks, tracing tools, and hosted platforms. Those tools are useful, but the evaluation contract itself should be portable.

ECP separates the protocol from the platform:

- run evals locally or in CI
- wrap agents built with plain Python, LangChain, LlamaIndex, CrewAI, or PydanticAI
- grade final outputs, tool calls, and `evaluation_context`
- emit JSON and HTML reports that other systems can ingest
- implement the same JSON-RPC contract in another language or runtime

## What ECP Checks

Most evals start with the final answer. ECP also checks the behavior behind that answer.

| Evaluation Need | ECP Surface |
| --- | --- |
| Did the user-visible answer satisfy the task? | `public_output` |
| Did the agent call the required tool with the right arguments? | `tool_calls` |
| Did the agent expose evaluator-safe audit evidence? | `evaluation_context` |
| Can this run in CI and fail a build? | `ecp run --manifest ...` |

`private_thought` is still accepted as a compatibility alias, but new agents should use `evaluation_context`. ECP is not asking providers to expose raw chain-of-thought; it is asking agents to expose evaluator-safe evidence.

## Developer Path

```bash
pip install "ecp-runtime==0.3.1" "ecp-sdk==0.3.1"
ecp init
ecp validate ecp_eval/manifest.yaml
ecp run --manifest ecp_eval/manifest.yaml --json
```

For a realistic example that shows why output-only evals are not enough:

```bash
ecp run --manifest examples/customer_support_demo/manifest.yaml --report report.html
```

## What Is In This Repo

- `sdk/python/src/ecp` - Python SDK for implementing ECP agents
- `runtime/python/src/ecp_runtime` - reference runtime and `ecp` CLI
- `examples/customer_support_demo` - flagship policy/tool-use demo
- `examples/*_demo` - framework integrations
- `schema/` - JSON Schema contracts for manifests, agent results, tool calls, and reports
- `spec/` and `docs/spec.md` - protocol specification

Go to **Quickstart** to run your first eval, **Examples** for integration patterns, or **Specification** to implement ECP in another runtime.

