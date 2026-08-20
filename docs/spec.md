# Specification

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Protocol Source](https://github.com/evaluation-context-protocol/ecp/blob/main/spec/protocol.md)

## Overview

ECP is JSON-RPC 2.0 over stdio or Streamable HTTP. The runtime sends `agent/initialize`, `agent/step`, and `agent/reset`. The agent returns structured results containing public output, evaluator-safe audit context, and tool usage.

## Transports

The default transport is stdio: the runtime spawns the agent process and exchanges one JSON-RPC object per line over standard input and output.

For Streamable HTTP, the agent runs as an HTTP server and exposes one endpoint, conventionally `/ecp`. Clients `POST` JSON-RPC messages with `Accept: application/json, text/event-stream`; request responses may be JSON or SSE, while notifications return `202 Accepted`. Servers that do not support server-initiated SSE streams return `405 Method Not Allowed` for `GET`.

## Methods

### agent/initialize

**Params**: `config` (object, optional)

**Result**: `{ name, capabilities }`

### agent/step

**Params**: `input` (string)

**Result**:

- `status`: `done` or `paused`
- `public_output`: string or null
- `evaluation_context`: string or null
- `private_thought`: deprecated compatibility alias for `evaluation_context`
- `tool_calls`: array or null
- `logs`: optional evaluator-visible execution logs or null
- `usage`: optional token accounting or null

Tool call format:

```json
{ "name": "calculator", "arguments": { "expression": "2+2" } }
```

Usage format. All fields are optional and must be non-negative integers when present. Agents that cannot observe token counts should omit `usage` rather than reporting zeros, so the runtime can tell "not reported" from "reported as zero":

```json
{ "input_tokens": 1204, "output_tokens": 88, "total_tokens": 1292 }
```

### agent/reset

**Params**: none

**Result**: `true`

## Manifest

The runtime reads a YAML manifest describing scenarios and graders.

Supported graders:

- `text_match` (contains, equals, does_not_contain, regex)
- `llm_judge` (requires `OPENAI_API_KEY`)
- `tool_usage` (name + argument subset match)

Text and LLM graders can target `public_output`, `evaluation_context`, or the deprecated `private_thought` alias.

`llm_judge` model can be configured with `ECP_LLM_JUDGE_MODEL` (default: `gpt-4o-mini`). `llm_judge` temperature can be configured with `ECP_LLM_JUDGE_TEMPERATURE` (default: `0`).

Validate a manifest without running an agent:

```bash
ecp validate examples/customer_support_demo/manifest.yaml
```

## Execution Boundaries

A runtime must bound agent execution so a hung or looping agent cannot pin a CI pipeline. Two independent limits apply:

- **Per-RPC timeout** (`--timeout`, `ECP_RPC_TIMEOUT`, default 30s): the maximum wait for a single response.
- **Wall-clock budget** (`--max-duration`, `ECP_MAX_DURATION`, unset by default): a ceiling on the whole run. Not redundant with the per-RPC timeout, because an agent answering just inside that timeout on every step can still run for hours.

When either limit is breached, or the agent crashes or breaks the contract, the runtime **degrades rather than aborts**. The affected step is recorded as failed, remaining steps in that scenario are marked skipped, and the run continues with the next scenario against a fresh agent. A step that produced no result still contributes at least one failed check, so a timeout can never be counted as a pass.

Each step carries an `exit_reason`:

| `exit_reason` | Meaning |
| --- | --- |
| `ok` | The agent answered and graders ran. |
| `timeout` | No response inside the per-RPC timeout. |
| `transport_error` | The agent crashed, closed the stream, or was unreachable. |
| `protocol_error` | The agent replied, but the reply violates the specification. |
| `agent_error` | The agent returned a JSON-RPC error response. |
| `max_duration_exceeded` | The wall-clock budget was exhausted. |
| `skipped` | The step never ran because an earlier step in the scenario failed. |

## Reports

The runtime can generate HTML and JSON reports:

```bash
ecp run --manifest examples/customer_support_demo/manifest.yaml --report report.html
ecp run --manifest examples/customer_support_demo/manifest.yaml --json
ecp run --manifest examples/customer_support_demo/manifest.yaml --json-out report.json
```

## Audit Record

Every run produces a structured audit record, embedded under the `audit` key of the JSON report and writable standalone:

```bash
ecp run --manifest examples/customer_support_demo/manifest.yaml --audit-out ecp_audit.json
```

It records a unique `run_id`, start and finish timestamps, the manifest path and its SHA-256 digest, the resolved `target`, agent metadata from `agent/initialize`, the configured limits, per-step latency and `exit_reason`, aggregated token `usage`, and pass/fail totals.

Two properties make it auditable rather than merely informative: the manifest digest ties results to exact inputs, and `steps_planned` versus `steps_executed` reveals a run that degraded instead of one that genuinely passed.

```json
{
  "exit_reason": "timeout",
  "manifest": { "digest": "sha256:c8a39311...", "target": "python agent.py" },
  "agent": { "name": "SupportAgent", "capabilities": {} },
  "totals": { "steps_planned": 4, "steps_executed": 2, "steps_failed": 1, "steps_skipped": 1 },
  "latency": { "total_ms": 0.54, "max_ms": 0.292, "p95_ms": 0.292 },
  "usage": { "input_tokens": 22, "output_tokens": 8, "total_tokens": 30 }
}
```

Latency aggregates only steps that actually executed, so one timeout does not skew the percentiles.

## Schemas

Machine-readable JSON Schemas live in `schema/`:

- `schema/manifest.schema.json`
- `schema/agent-result.schema.json`
- `schema/tool-call.schema.json`
- `schema/report.schema.json`
- `schema/audit.schema.json`
