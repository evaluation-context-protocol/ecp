# ECP-0002: Execution Traces And The Inspector

Status: Draft — for discussion
Author: ECP maintainers
Depends on: [ECP-0001](0001-protocol-maturity.md) phase 1 (capabilities)

## Summary

The Inspector today lists manifests from `examples/`, runs one, and shows
pass/fail per grader. The thing people actually want from it — "five agents,
ten tools, one question: show me what actually happened, what was called
correctly, and what the agent made up" — **is not something ECP can currently
express.**

That is a data model gap, not a UI gap. No amount of Inspector work produces a
call path, because the protocol carries no path. This proposal adds the missing
protocol surface first, then rebuilds the Inspector on top of it, then covers
interop with other eval tooling.

---

## Part 0 — What exists today

`server/src/server.js` (~500 lines, zero dependencies) plus a static client.
Two distinct modes:

**Evaluation mode.** Scans for `manifest.yaml` files, lists them, and on "Run"
spawns `python -m ecp_runtime.cli run --manifest X --json --no-fail-on-error`,
polls a job, and renders scenario → step → grader results.

**Session mode.** Opens a live stdio or HTTP JSON-RPC session against the agent
and lets you fire `agent/step` and `agent/reset` by hand, showing raw responses
and logs. This is the direct MCP-Inspector analogue and is the more
differentiated half.

### Honest limitations

| Issue | Detail |
| --- | --- |
| **Only reads `examples/`** | `EXAMPLES_ROOT` is hardcoded. A developer cannot point it at their own manifest. It is a demo *of* the Inspector, not a usable tool. |
| **Only runs from a repo checkout** | Paths are `REPO_ROOT`-relative and it injects `runtime/python/src` onto `PYTHONPATH`. There is no `npx` story. |
| **Hand-rolled YAML parser** | `parseManifest` is ~60 lines of indentation heuristics with an `indent >= 14` magic number. It cannot parse the flow-style graders used in `examples/crewai_demo/manifest.yaml`, datasets, or multi-line strings. |
| **Fragile result parsing** | Runtime JSON is recovered with `indexOf("{")` … `lastIndexOf("}")` over stdout. Any log line containing braces corrupts it. |
| **No progress** | `progress` goes `0` → `1`. A fifty-scenario run shows nothing until it finishes. |
| **Ignores the audit record** | Latency, token usage, `exit_reason`, and degraded-run state all exist now and none are shown. |
| **Read-only** | No editing a grader and re-running. The tightest useful loop — tweak, re-run, compare — is absent. |
| **Not in CI** | No tests, not built or linted by any workflow. |

---

## Part 1 — Why the "call path" view is impossible today

`tool_calls` is a flat list of `{name, arguments}`. Three things are missing.

### 1. No tool inventory, so hallucination is undetectable

To claim a tool was hallucinated you must know which tools exist. **ECP never
learns the agent's tool inventory.** A call to `lookup_order` and a call to
`lookup_ordr` are both just strings in a list. The runtime cannot tell a real
tool from an invented one, so the single most requested view cannot be built.

### 2. No attribution, so multi-agent structure is invisible

`examples/two_agent_demo` models its sub-agents *as tool calls* named
`planner_agent` and `writer_agent`. That is a convention the demo invented, not
a protocol concept. Nothing says which agent made a call, or that one agent
delegated to another. Five agents and ten tools collapse into one flat list of
fifteen names.

### 3. No outcomes and no edges

A tool call records `{name, arguments}` — not whether it **succeeded**, what it
returned, how long it took, or what triggered it. So "called six tools
correctly" is not derivable: ECP only knows the agent *claimed* to call them.

That last point deserves emphasis. **ECP records self-reported behaviour.** The
agent (via its adapter) says what it did; nothing verifies it. That is a
reasonable design — it is what keeps ECP framework-neutral — but it should be
stated in the spec, because "the agent hallucinated a tool" and "the adapter
failed to report a tool" are indistinguishable today, and we already know the
second happens (see ECP-0003 work on adapter conformance).

---

## Part 2 — Proposal: tool inventory and call structure

### 2.1 Declared tool inventory

Extends the `tool_calls` capability from ECP-0001:

```json
{
  "capabilities": {
    "tool_calls": {
      "inventory": [
        { "name": "lookup_order", "description": "Fetch an order by id" },
        { "name": "check_refund_policy", "description": "Policy for an order" },
        { "name": "issue_refund", "description": "Issue a refund" }
      ]
    }
  }
}
```

The runtime then classifies every reported call as **declared** or
**undeclared**, and the audit record carries the counts.

**Terminology matters here.** We report `undeclared`, not `hallucinated`. An
agent may legitimately call a dynamically-registered tool. Hallucination is an
*interpretation* of undeclared calls that a human or a grader makes; the
protocol should report the fact, not the judgement.

New grader:

```yaml
- type: tool_inventory
  condition: no_undeclared_calls
```

### 2.2 Richer tool calls

Every field additive and optional, so existing agents stay valid:

```json
{
  "id": "call_2",
  "parent_id": "call_1",
  "kind": "tool",
  "agent": "writer",
  "name": "lookup_order",
  "arguments": { "order_id": "A100" },
  "status": "ok",
  "error": null,
  "duration_ms": 12.3,
  "result_summary": "Order A100, purchased 5 days ago"
}
```

- `id` / `parent_id` give the call **graph** — this is what makes a path view
  possible. Absent `parent_id` means a root call.
- `agent` gives **attribution** in multi-agent systems.
- `kind` is `"tool"` or `"agent"`, so delegation and tool use live in one graph
  with a discriminator, rather than in two parallel arrays. Frameworks generally
  implement delegation *as* a tool call, so this matches reality.
- `status` / `error` make "called correctly" answerable.
- `result_summary` is **evaluator-safe by contract** — a short summary, never
  the raw tool result. Raw results are the most likely place for PII to leak
  into CI artifacts, and we already have that problem with `evaluation_context`.

With this, the view the user described becomes a straightforward render:

```
Step 1  "I want a refund for order A100"                        1,204ms
│
├─ agent  planner                                     ok         310ms
│   ├─ tool  lookup_order {order_id: "A100"}          ok          41ms  declared
│   └─ tool  check_refund_policy {order_id: "A100"}   ok          28ms  declared
│
└─ agent  writer                                      ok         890ms
    ├─ tool  fetch_customer_tier {id: "A100"}         error       12ms  UNDECLARED
    └─ tool  issue_refund {order_id: "A100"}          ok          63ms  declared  ← policy grader FAILED

2 agents · 4 tools · 3 ok · 1 error · 1 undeclared
```

### 2.3 Compatibility

Entirely additive. Agents that report `{name, arguments}` keep working and
simply produce a flat, single-level path. Adapters gain the richer fields
opportunistically — PydanticAI and LangChain both expose call ids and errors
already, so they can populate more than CrewAI can.

The `tool_usage` grader is unchanged. New graders (`tool_sequence` from
ECP-0001 phase 2, `tool_inventory` here) build on the new fields.

---

## Part 3 — Proposal: the Inspector as a real tool

### 3.1 Make it usable outside this repo

The blocking issue. Publish as `@ecp/inspector`, runnable via `npx`, operating
on the user's project:

```bash
npx @ecp/inspector                       # discover manifests under cwd
npx @ecp/inspector --manifest evals/support.yaml
```

It should shell out to whatever `ecp` is on `PATH` rather than injecting
`PYTHONPATH` into a repo checkout.

### 3.2 Stop parsing YAML in JavaScript

Delete `parseManifest`. Call `ecp validate --json` and consume the runtime's
own parsed manifest. One parser, one source of truth, and the Inspector
automatically understands datasets, flow style, and every future manifest
feature for free.

This requires adding `--json` output to `ecp validate`, which is small and
useful independently.

### 3.3 Streaming progress

`ecp run --progress` emits NDJSON events on stderr:

```json
{"event":"scenario_start","name":"Refund inside window","index":1,"total":12}
{"event":"step_done","scenario":1,"step":2,"status":"ok","duration_ms":812}
{"event":"run_done","passed":31,"total":34,"exit_reason":"ok"}
```

The Inspector streams these instead of polling a job that reports `0` then `1`.
This also benefits plain CLI users on long runs, who currently get silence.

### 3.4 Surface what we already collect

The audit record has latency, tokens, `exit_reason`, and planned-vs-executed
steps. Show them. A degraded run — timeout, skipped steps — should be visually
distinct from a clean failing run, because they mean completely different
things and are currently rendered identically.

### 3.5 The edit-and-rerun loop

The thing that makes an inspector sticky is a tight loop: tweak a grader,
re-run, see what changed. Editing the manifest in the UI plus a run-over-run
diff ("3 checks newly failing, 1 newly passing") is higher value than any
individual view, including the trace.

### 3.6 Read result payloads, not stdout

Run with `--json-out` and `--audit-out` to temp files and read those, instead of
brace-scanning stdout.

---

## Part 4 — Interop with other eval frameworks

Three tiers, in order of how much work they are and how far they reach.

### 4.1 The file is the integration (works today)

`--json-out` and `--audit-out` are schema-validated artifacts. Any tool can
consume them. This is the honest baseline and should be documented as the
primary integration path rather than treated as a fallback.

### 4.2 OpenTelemetry export (recommended)

Rather than writing N bespoke exporters, emit OTel spans following the GenAI
semantic conventions. One integration reaches Langfuse, Arize, Datadog,
Honeycomb, Braintrust, and anything else that speaks OTLP.

The call-graph work in Part 2 is what makes this possible: `id`/`parent_id`
map directly onto span/parent-span, `duration_ms` onto span duration,
`status`/`error` onto span status. **The trace view and OTel export are the same
underlying model** — build the model once and get both.

```bash
ecp run --manifest evals/support.yaml --otlp-endpoint http://localhost:4318
```

### 4.3 Native test-framework integration (partly exists)

The pytest plugin already lets ECP run inside an existing suite. The equivalent
for Vitest/Jest arrives with the TypeScript SDK. This is the "use ECP without
adopting ECP's runner" path and is worth promoting more loudly — many teams will
never run `ecp run`.

The existing `--export langsmith` should probably be **deprecated** in favour of
4.2. It currently creates runs with only input and output, dropping tool calls
and evaluation context, so it under-represents ECP to the one audience that
already understands evals.

---

## Sequencing

1. Tool inventory (2.1) — small, and it unblocks the most-requested view. Ships
   with ECP-0001 capabilities.
2. Inspector portability (3.1, 3.2, 3.6) — turns a demo into a tool. Independent
   of everything else.
3. Richer tool calls (2.2) — the protocol work behind the path view.
4. Progress streaming (3.3) and audit surfacing (3.4).
5. Trace view and OTel export (2.2 consumers, 4.2) — same model, two outputs.
6. Edit-and-rerun (3.5).

## Open questions

- **Is `agent` a string or a structured reference?** A string is simple; a
  reference allows per-agent capability declaration in nested systems. Leaning
  string until someone needs more.
- **Should `result_summary` exist at all?** It is genuinely useful for debugging
  and is a PII risk by construction. Options: omit it, gate it behind a
  capability, or make redaction mandatory before it reaches artifacts.
- **Do we verify anything?** Everything here is still self-reported. A stricter
  mode where the runtime observes tool calls directly would require the proxy /
  bidirectional work deferred in ECP-0001. Worth deciding whether "trusted
  self-report" is a permanent design stance or a temporary one.
- **Does the Inspector belong in this repo?** A published npm package with its
  own release cadence may want its own repository, like the TypeScript SDK.
