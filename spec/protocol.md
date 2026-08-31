# Evaluation Context Protocol (ECP) Specification

Version: 1.0-draft
Status: Experimental

## 1. Overview

ECP defines a simple JSON-RPC 2.0 interface between:

- **Runtime**: the test runner that executes scenarios and graders.
- **Agent**: the system under test, running as a child process or HTTP service.

The protocol is intentionally platform-neutral. A runtime, CI system, eval platform, or local tool can all consume the same agent result contract.

## 2. Transports

- **Default transport**: stdio. The runtime spawns the agent process.
- **Remote/local service transport**: Streamable HTTP.
- **Protocol**: JSON-RPC 2.0.

### 2.1 stdio

For stdio, the runtime launches the agent and communicates over standard input and standard output. Each request is a single JSON-RPC object on its own line; each response is a single JSON-RPC object on its own line.

### 2.2 Streamable HTTP

For Streamable HTTP, the agent runs as an independent HTTP server and exposes one endpoint for ECP JSON-RPC messages, conventionally `/ecp`.

- Clients send each JSON-RPC message with `POST` to the ECP endpoint.
- `POST` requests use `Content-Type: application/json`.
- Clients include `Accept: application/json, text/event-stream`.
- If a `POST` contains one or more JSON-RPC requests, the server returns either `Content-Type: application/json` with the JSON-RPC response object or `Content-Type: text/event-stream` with JSON-RPC responses in SSE `data` events.
- If a `POST` contains only JSON-RPC notifications or responses, the server returns `202 Accepted` with no body.
- Clients may send `GET` with `Accept: text/event-stream` to open a server-to-client SSE stream. Servers that do not support server-initiated messages return `405 Method Not Allowed`.
- Local HTTP servers should bind to `127.0.0.1` by default and validate `Origin` headers.

The reference Python SDK currently returns JSON responses for `POST` requests and `405 Method Not Allowed` for `GET` because ECP does not yet define server-initiated messages.

## 3. Methods

### 3.1 `agent/initialize`

**Direction**: Runtime -> Agent

**Purpose**: Set up the agent and return metadata.

**Params**:

- `protocol_version` (string): highest protocol version supported by the runtime, formatted as `MAJOR.MINOR`.
- `config` (object, optional): configuration from the runtime.

**Result**:

- `name` (string): agent display name.
- `protocol_version` (string): protocol version selected for this session, formatted as `MAJOR.MINOR`.
- `capabilities` (object): reserved for future use.

#### Protocol version negotiation

Protocol versions are independent of SDK and runtime package versions. The runtime sends the highest protocol version it supports, and the agent responds with the version it will use for the session.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "agent/initialize",
  "params": { "protocol_version": "1.0", "config": {} }
}
```

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "name": "SupportAgent",
    "protocol_version": "1.0",
    "capabilities": {}
  }
}
```

The negotiation rules are:

1. A different major version is incompatible. The agent returns JSON-RPC error `-32001` (`VERSION_UNSUPPORTED`), or the runtime aborts before executing steps if an incompatible result is received.
2. When only minor versions differ, both sides use the lower minor version.
3. A versionless agent is treated as legacy protocol `0.1`. The runtime continues with a single warning per run.
4. A versionless runtime remains compatible with the reference SDK; the SDK returns its current protocol version as an additive result field.

### 3.2 `agent/step`

**Direction**: Runtime -> Agent

**Purpose**: Execute a single evaluation step.

**Params**:

- `input` (string): the step input text.

**Result**:

- `status` (string): `done` or `paused`.
- `public_output` (string | null): user-visible output.
- `evaluation_context` (string | null): evaluator-safe audit context, reasoning summary, policy evidence, or trace summary.
- `private_thought` (string | null): deprecated compatibility alias for `evaluation_context`.
- `tool_calls` (array | null): tools the agent invoked.
- `logs` (string | null): optional evaluator-visible execution logs.
- `usage` (object | null): optional token accounting for this step.

ECP does not require raw chain-of-thought. New agents should use `evaluation_context` for concise evaluator-safe evidence.

**Usage format**:

```json
{ "input_tokens": 1204, "output_tokens": 88, "total_tokens": 1292 }
```

All three fields are optional and MUST be non-negative integers when present. Agents that cannot observe token counts SHOULD omit `usage` entirely rather than reporting zeros; the runtime distinguishes "not reported" from "reported as zero" in its audit record.

**Tool call format**:

```json
{
  "name": "calculator",
  "arguments": { "expression": "2+2" }
}
```

### 3.3 `agent/reset`

**Direction**: Runtime -> Agent

**Purpose**: Clear transient state between scenarios.

**Params**: none

**Result**: `true`

## 4. JSON-RPC Example

```json
{
  "jsonrpc": "2.0",
  "method": "agent/step",
  "params": { "input": "Refund order A100" },
  "id": 1
}
```

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "done",
    "public_output": "Order A100 is eligible for a refund.",
    "evaluation_context": "Checked order A100 and confirmed it is inside the 30-day refund window.",
    "tool_calls": [
      { "name": "lookup_order", "arguments": { "order_id": "A100" } },
      { "name": "check_refund_policy", "arguments": { "order_id": "A100" } }
    ]
  }
}
```

## 5. Manifest

The runtime reads a YAML manifest to define scenarios and graders. Core fields:

- `manifest_version` (string)
- `name` (string)
- `target` (string command or HTTP endpoint)
- `scenarios` (list of steps)

Supported graders:

- `text_match`: contains, equals, does_not_contain, regex
- `llm_judge`: prompt-based evaluation
- `tool_usage`: verifies tool call name and argument subset

Text and LLM graders can target `public_output`, `evaluation_context`, or deprecated `private_thought`.

## 6. Execution Boundaries

A runtime MUST bound agent execution so a hung or looping agent cannot pin a CI pipeline indefinitely. Two independent limits apply:

- **Per-RPC timeout**: the maximum time to wait for a single response. The reference runtime defaults to 30s (`--timeout`, `ECP_RPC_TIMEOUT`).
- **Wall-clock budget**: an optional ceiling on the total run (`--max-duration`, `ECP_MAX_DURATION`). This is not redundant with the per-RPC timeout: an agent that answers just inside the timeout on every step can still run for hours.

When either limit is breached, or the agent crashes or violates the contract, the runtime MUST **degrade rather than abort**. The affected step is recorded as failed, remaining steps in that scenario are recorded as skipped, and the run continues with the next scenario. A step that did not produce a result MUST still contribute at least one failed check, so a timeout can never be counted as a pass.

Each step carries an `exit_reason`:

| `exit_reason` | Meaning |
| --- | --- |
| `ok` | The agent answered and graders ran. |
| `timeout` | No response inside the per-RPC timeout. |
| `transport_error` | The agent crashed, closed the stream, or was unreachable. |
| `protocol_error` | The agent replied, but the reply violates this specification. |
| `agent_error` | The agent returned a JSON-RPC error response. |
| `max_duration_exceeded` | The wall-clock budget was exhausted. |
| `skipped` | The step never ran because an earlier step in the scenario failed. |

Because each scenario gets a fresh agent, a failure in one scenario does not contaminate the next.

## 7. Audit Record

After every run, a runtime SHOULD emit a structured audit record describing what was executed. The reference runtime writes it with `ecp run --audit-out ecp_audit.json`, and also embeds it under the `audit` key of the JSON report.

The record covers: a unique `run_id`, start/finish timestamps, the manifest path and its SHA-256 digest, the resolved `target`, agent metadata from `agent/initialize`, the configured limits, per-step latency and `exit_reason`, aggregated token `usage`, and pass/fail totals. The schema is `schema/audit.schema.json`.

Two properties make it auditable rather than merely informative: the manifest digest ties results to exact inputs, and `steps_planned` versus `steps_executed` reveals a run that degraded instead of silently reporting a high pass rate over fewer steps.

## 8. Schemas And Conformance

Machine-readable contracts live in `schema/`:

- `schema/initialize-params.schema.json`
- `schema/initialize-result.schema.json`
- `schema/agent-result.schema.json`
- `schema/tool-call.schema.json`
- `schema/manifest.schema.json`
- `schema/report.schema.json`
- `schema/audit.schema.json`

Protocol implementers can run:

```bash
ecp conformance --target "python examples/customer_support_demo/agent.py"
```
