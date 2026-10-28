# Evaluation Context Protocol (ECP)

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Quickstart](quickstart.md) | [Specification](spec.md)

**Portable evaluations for AI agents.**

ECP is a vendor-neutral protocol for testing agent outputs, tool calls, and evaluator-visible audit context across frameworks, models, eval platforms, and CI systems.

Think of it as the evaluation contract layer: MCP gives agents a common way to use tools; ECP gives evaluators a common way to inspect what an agent returned, what tools it used, and what audit evidence it exposed.

## Where ECP Sits

ECP is a protocol between agents and the tools that evaluate them. It is not another evaluation framework.

- **Agent side.** Adapters put an agent built in CrewAI, LangChain, PydanticAI, LlamaIndex or plain Python onto one contract: what it said (`public_output`), what it did (`tool_calls`), and evidence for the evaluator (`evaluation_context`, `usage`).
- **Evaluator side.** Any tool that speaks ECP can test any of those agents without framework code: ECP's own `ecp run`, [Promptfoo and DeepEval](integrations.md), or your own harness.

Change the agent's framework and the evaluation does not change, only the command that starts the agent. Change the evaluation tool and the agent does not change.

ECP's runtime includes graders (`llm_judge`, `tool_usage`, `not_called`) so the protocol works on its own, but grading is not what ECP is for. Use the judge you already trust; ECP makes sure it can see what the agent did.

### Why the contract carries tool calls

A refund agent that must never issue refunds is pushed by a customer, calls `issue_refund`, and replies "your request has been passed to our team." The reply is fine. Only the tool call shows the refund went out. In 90 measured runs with 9 real refunds, checks on the reply caught 1 to 4 of them depending on the tool; checks on the tool calls caught all 9. That is why `tool_calls` is part of the contract, and why ECP will not pass a "never called X" check for an agent that does not report its tool calls.

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
pip install "ecp-runtime==0.10.0" "ecp-sdk==0.10.0"
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
- `integrations/` and `ecp_runtime.integrations` - Promptfoo provider and DeepEval bridge
- `experiments/` - the studies behind the claims on this page
- `schema/` - JSON Schema contracts for manifests, agent results, tool calls, and reports
- `spec/` and `docs/spec.md` - protocol specification

Go to **Quickstart** to run your first eval, **Examples** for integration patterns, or **Specification** to implement ECP in another runtime.

