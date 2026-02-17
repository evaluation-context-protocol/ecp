# Specification`r`n`r`n[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Protocol Source](https://github.com/evaluation-context-protocol/ecp/blob/main/spec/protocol.md)`r`n
## Overview

ECP is JSON-RPC 2.0 over stdio. The runtime spawns the agent process and sends requests for `initialize`, `step`, and `reset`. The agent returns structured results containing public output, private reasoning, and tool usage.

## Methods

### agent/initialize

**Params**: `config` (object, optional)

**Result**: `{ name, capabilities }`

### agent/step

**Params**: `input` (string)

**Result**:

- `status`: `done` or `paused`
- `public_output`: string or null
- `private_thought`: string or null
- `tool_calls`: array or null

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

See `examples/langchain_demo/manifest.yaml` for a minimal example.

## Reports

The runtime can optionally generate a single HTML report for a run:

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml --report .\report.html
```

The runtime can also emit a JSON report (useful for CI):

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml --json
```

