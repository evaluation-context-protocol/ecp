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

Tool call format:

```json
{ "name": "calculator", "arguments": { "expression": "2+2" } }
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

## Reports

The runtime can generate HTML and JSON reports:

```bash
ecp run --manifest examples/customer_support_demo/manifest.yaml --report report.html
ecp run --manifest examples/customer_support_demo/manifest.yaml --json
ecp run --manifest examples/customer_support_demo/manifest.yaml --json-out report.json
```

## Schemas

Machine-readable JSON Schemas live in `schema/`:

- `schema/manifest.schema.json`
- `schema/agent-result.schema.json`
- `schema/tool-call.schema.json`
- `schema/report.schema.json`
