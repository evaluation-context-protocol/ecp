# Evaluation Context Protocol (ECP) Specification

Version: 0.2.3-draft
Status: Experimental

## 1. Overview

ECP defines a simple JSON-RPC 2.0 interface between:

- **Runtime**: the test runner that executes scenarios and graders.
- **Agent**: the system under test, running as a child process.

The runtime launches the agent and communicates over stdio. Each request is a single JSON-RPC object on its own line; each response is a single JSON-RPC object on its own line.

## 2. Transport

- **Default transport**: stdio (runtime spawns the agent process).
- **Protocol**: JSON-RPC 2.0.

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
- `private_thought` (string | null): evaluator-only reasoning.
- `tool_calls` (array | null): tools the agent invoked.

**Tool call format** (recommended):

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

## 4. JSON-RPC Examples

```json
// Request
{ "jsonrpc": "2.0", "method": "agent/step", "params": { "input": "Hello" }, "id": 1 }

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "done",
    "public_output": "Hi there!",
    "private_thought": "Greet the user.",
    "tool_calls": null
  }
}
```

## 5. Manifest (Runtime)

The runtime reads a YAML manifest to define scenarios and graders. Core fields:

- `manifest_version` (string)
- `name` (string)
- `target` (string command to launch the agent)
- `scenarios` (list of steps)

Supported graders:

- `text_match`: contains, equals, does_not_contain, regex
- `llm_judge`: prompt-based evaluation (requires `OPENAI_API_KEY`)
- `tool_usage`: verifies tool call name and argument subset

See `examples/langchain_demo/manifest.yaml` for a minimal manifest.

