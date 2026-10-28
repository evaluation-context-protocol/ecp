# Evaluation Context Protocol (ECP)

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Quickstart](quickstart.md) | [Specification](spec.md)

**Portable evaluations for AI agents.**

ECP is a vendor-neutral protocol for testing agent outputs, tool calls, and evaluator-visible audit context across frameworks, models, eval platforms, and CI systems.

Think of it as the evaluation contract layer: MCP gives agents a common way to use tools; ECP gives evaluators a common way to inspect what an agent returned, what tools it used, and what audit evidence it exposed.

## What ECP does, and why use it

ECP checks what an agent **did**, not only what it **said**.

Take a refund bot that must never issue refunds without approval. Under pressure it calls `issue_refund`, then tells the customer "your request has been passed to our team." The reply looks fine. A check on the reply passes it. ECP also receives the list of tools the agent called, so `condition: not_called` on `issue_refund` fails the run.

That is the case ECP was measured on ([evidence](evidence.md)). In 90 live runs, 9 really issued a refund. Checks that read only the reply caught between 1 and 4 of them, depending on the tool. Checks on the tool calls caught all 9, with no false alarms on the other 81.

Use ECP when:

- the risk is an **action** (a refund, a deletion, an email), not a wording problem;
- you want **one test definition** that works whether the agent is built in CrewAI, LangChain, PydanticAI, LlamaIndex or plain Python (verified on those four, once two adapter bugs were fixed);
- you want a prohibition that **fails safe**: if an agent does not report its tool calls, ECP refuses to pass "never called X" rather than passing it because nothing was reported.

What ECP is not: a better judge of reply quality. On the same cases, its LLM judge scored the same as DeepEval's and Promptfoo's, and DeepEval has more tool-call checks (allow-lists, ordering). Pair ECP with whichever judge you prefer; ECP's job is carrying the tool calls and evidence to the grader in a common form.

Limits of the evidence: one cheap model, small samples, and defects produced by a prompt written to cause them. See [Evidence](evidence.md) for what was and was not tested.

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
- `schema/` - JSON Schema contracts for manifests, agent results, tool calls, and reports
- `spec/` and `docs/spec.md` - protocol specification

Go to **Quickstart** to run your first eval, **Examples** for integration patterns, or **Specification** to implement ECP in another runtime.

