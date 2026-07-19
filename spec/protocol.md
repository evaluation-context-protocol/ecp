# Evaluation Context Protocol (ECP) Specification

Version: 0.3.1-draft
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

- `config` (object, optional): configuration from the runtime.

**Result**:

- `name` (string): agent display name.
- `capabilities` (object): reserved for future use.

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

ECP does not require raw chain-of-thought. New agents should use `evaluation_context` for concise evaluator-safe evidence.

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

## 6. Schemas And Conformance

JSON Schemas live in `schema/`. Protocol implementers can run:

```bash
ecp conformance --target "python examples/customer_support_demo/agent.py"
```
