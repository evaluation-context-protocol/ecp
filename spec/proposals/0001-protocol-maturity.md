# ECP-0001: Protocol Maturity Roadmap

Status: Draft — for discussion
Author: ECP maintainers
Targets: protocol `1.0`, runtime `1.x`

## Summary

Four phases that take ECP from "a working eval runner with a protocol attached"
to "a protocol other people can build on, and a benchmark others can trust."

They are strictly ordered. Each depends on the one before it, and the last is
the one everyone wants to do first.

| Phase | Work | Why it comes here |
| --- | --- | --- |
| 1. Now | Version negotiation and real capabilities | The window closes as adoption grows. Everything else needs a safe way to evolve. |
| 2. Next | Grader depth | Makes ECP a policy-testing tool rather than a string matcher — the story the README already tells. |
| 3. Then | Determinism and variance | Unglamorous prerequisite for any comparable number. |
| 4. Then, and only then | Publishable benchmarks | Credible only on top of 1–3. |

The temptation is to jump to phase 4. A leaderboard built on single-run,
unpinned-judge, unversioned manifests produces numbers nobody can reproduce —
and a protocol only gets to be wrong about that once.

---

# Phase 1 — Version negotiation and capabilities

## The problem

**There is no protocol version anywhere in the wire format.** `agent/initialize`
exchanges a name and an empty object. A runtime cannot tell whether it is
talking to an agent built against today's spec or one from six months ago, so
there is no safe way to ever make a breaking change. We detect incompatibility
by watching things fail strangely.

**`capabilities` is a dead field.** The runtime validates it is an object
([conformance.py](../../runtime/python/src/ecp_runtime/conformance.py)) and then
ignores it. Nothing is ever declared and nothing ever reads it.

That has concrete costs today:

- A manifest with `tool_usage` graders run against an agent that cannot report
  tool calls fails with `"No tool_calls present"` on every step. That is
  **indistinguishable from an agent that legitimately used no tools.** One is a
  broken integration, the other is a real test failure, and we report them the
  same way.
- `agent/reset` returns `true` unconditionally. In
  [server.py](../../sdk/python/src/ecp/server.py), `_handle_reset` runs the hook
  if one is registered and returns `true` either way — so an agent with no reset
  support claims successful reset, and scenario isolation silently does not
  happen.
- `params.config` is documented in the spec and **dropped entirely** by
  `_handle_init`. Either it means something or it should not be in the spec.

## Proposal

### Version exchange

Both directions of `agent/initialize` carry `protocol_version`, a
`MAJOR.MINOR` string.

- **MAJOR** increments on breaking changes. Different major versions are
  incompatible.
- **MINOR** increments on additive changes. A runtime speaking `1.2` must work
  with an agent speaking `1.0`, and vice versa, degraded to the lower minor.

This is deliberately **not** the package version. `ecp-runtime` is at `0.9.0`
and moves weekly; the protocol should move yearly. Coupling them was already a
source of drift in the docs.

Request:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "agent/initialize",
  "params": {
    "protocol_version": "1.0",
    "runtime": { "name": "ecp-runtime", "version": "0.9.0" },
    "capabilities": {},
    "config": {}
  }
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "name": "SupportAgent",
    "protocol_version": "1.0",
    "capabilities": {
      "tool_calls": {},
      "evaluation_context": {},
      "usage": {},
      "reset": {},
      "multi_turn": { "max_turns": 20 }
    }
  }
}
```

**Negotiation rules**

1. The runtime sends the highest version it speaks.
2. The agent responds with the version it will actually speak — the runtime's
   version if it supports it, otherwise its own highest.
3. If the majors differ, the runtime MUST abort the run with a clear error
   rather than proceeding.
4. If minors differ, both sides operate at the lower minor.

**Absence means legacy.** An agent that omits `protocol_version` is assumed to
speak `0.1` — every agent built against the current SDK. The runtime MUST
continue to drive those agents, warning once. This is the whole reason to do it
now rather than after there are thousands of them.

### Capabilities

Presence of a key means supported. The value is an options object, empty when
there are no options. This mirrors MCP and leaves room to add options without a
version bump.

Proposed agent capabilities, each motivated by something broken today:

| Capability | Meaning | Runtime behaviour when absent |
| --- | --- | --- |
| `tool_calls` | Reports tool invocations | Fail fast if the manifest has `tool_usage` graders |
| `evaluation_context` | Populates evaluator-safe context | Fail fast if a grader targets that field |
| `usage` | Reports token accounting | Audit `usage` reported as unavailable, not zero |
| `reset` | Honours `agent/reset` | Warn that scenario isolation is not guaranteed |
| `multi_turn` | Maintains state across steps within a scenario | Warn on multi-step scenarios |
| `deterministic` | Same input yields same output | Required by phase 4; absent means benchmark scores need `repeat` |

The payoff is the failure mode getting honest. Instead of:

```
FAIL | tool_usage on tool_calls — No tool_calls present.   (x40)
```

you get, once, before anything runs:

```
Manifest requires tool_usage graders, but agent 'SupportAgent' does not
declare the 'tool_calls' capability. Either the adapter is not reporting
tool calls, or this agent cannot be evaluated by this manifest.
```

**Unknown keys MUST be ignored** by both sides. That is what makes minor
versions additive.

**Vendor extensions** use an `x-` prefix with a vendor segment:
`x-acme.trace_export`. Reserved so a vendor can extend without collision and
without the core spec having to know.

### `config`

Keep it, define it, and wire it up: manifest-provided configuration passed
through to the agent, exposed via a new `@on_initialize` SDK hook. A manifest
gains an optional `agent_config` block. If we would not do this, `config` should
be struck from the spec instead of remaining documented and ignored.

### New error codes

Reserve an ECP range within the JSON-RPC implementation-defined space:

| Code | Name | Meaning |
| --- | --- | --- |
| `-32001` | `VERSION_UNSUPPORTED` | Major version mismatch |
| `-32002` | `CAPABILITY_REQUIRED` | Manifest needs a capability the agent lacks |
| `-32003` | `CONFIG_INVALID` | Agent rejected the supplied `config` |

Currently everything is `-32000`, so a runtime cannot distinguish "your agent
crashed" from "your agent refuses this configuration."

## Compatibility

Fully additive. Old agents omit the fields and keep working under the `0.1`
assumption. Old runtimes ignore fields they do not know. The SDK sets
`protocol_version` and infers capabilities from registered hooks, so most users
get this by upgrading.

The one behaviour change: `reset` capability makes the current
"always return `true`" a lie we stop telling. Agents without an `@on_reset` hook
will stop declaring `reset`, and the runtime will warn on multi-scenario runs.

## Open questions

- `MAJOR.MINOR` versus MCP's date-based versions. Dates avoid arguments about
  what counts as breaking; semver is easier to reason about. Leaning semver.
- Should the SDK infer capabilities from hooks, or require them explicit?
  Inference is friendlier and risks being wrong; explicit is honest and is
  boilerplate.
- Does `deterministic` belong here or in phase 3?

---

# Phase 2 — Grader depth

## The problem

Three graders: `text_match`, `llm_judge`, `tool_usage`. `tool_usage` can only
assert a tool **was** called. The README positions ECP as a policy and tool-use
testing tool, and the most important policy assertions cannot be written:

- "must **not** call `issue_refund`" — the single most valuable assertion for an
  agent with authority it should not exercise
- "`lookup_order` **before** `issue_refund`" — ordering, i.e. did it check before
  it acted
- structured output assertions — PydanticAI agents serialize JSON into
  `public_output`, so today you `contains`-match against JSON text
- cost and latency as pass/fail, now that the audit record carries both

## Proposal

Reuse the existing `condition` field, which `GraderConfig` already has for
`text_match`:

```yaml
# Negative assertion — the agent must not exercise authority it lacks
- type: tool_usage
  condition: not_called
  tool_name: issue_refund

# Ordering — it must check the policy before acting on it
- type: tool_sequence
  mode: ordered_subsequence      # or: exact, unordered_subset
  tools: [lookup_order, check_refund_policy, issue_refund]

# Structured output
- type: json_match
  field: public_output
  path: "$.refund.eligible"
  equals: true

# Budgets, from the phase-0 audit record
- type: budget
  max_latency_ms: 5000
  max_total_tokens: 8000
```

`json_match` needs a JSONPath dependency in the runtime; the SDK stays
zero-dependency.

`budget` graders make the audit record load-bearing rather than informational,
which is a good forcing function for keeping it accurate.

## Compatibility

Additive. New grader types and one new `condition` value. Existing manifests are
unaffected. Schema and the `GraderConfig` validator both need the new types, and
`ecp validate` should reject a `not_called` grader that also specifies
`arguments`, which is meaningless.

## Open questions

- Should `not_called` be a `condition` on `tool_usage` or its own grader type?
  Condition reuses machinery; a separate type reads better in YAML.
- `tool_sequence` default mode. `ordered_subsequence` is the forgiving choice
  and probably right — agents legitimately interleave other calls.

---

# Phase 3 — Determinism and variance

## The problem

**One run is not a score.** Agents are stochastic; the same manifest against the
same agent gives different results. Everything today reports a single pass rate
as if it were a measurement.

**`llm_judge` silently poisons comparability.** The judge model comes from
`ECP_LLM_JUDGE_MODEL` (default `gpt-4o-mini`) read from the environment at grade
time — it is not in the manifest, so it is not in the manifest digest. When the
provider updates that model, every historical score shifts and nothing in the
report records that anything changed.

`ecp trend` already does cross-run pass-rate analysis, but it compares runs
without any notion of expected variance, so it cannot distinguish noise from
regression.

## Proposal

**Repeats.** `--repeat N`, or per-scenario `repeat:`. The audit record gains a
`runs` array and a `variance` block: pass rate mean, standard deviation, and
min/max per check. A check that passes 3 of 5 times is reported as flaky rather
than as pass or fail.

**Pin the judge in the manifest**, not the environment:

```yaml
- type: llm_judge
  model: "gpt-4o-mini-2024-07-18"
  temperature: 0
  prompt: "Does the answer cite a policy?"
```

Environment variables become the fallback, not the source of truth. The pinned
model then lands inside the manifest digest, so a judge change produces a
different digest, which is exactly what we want.

**Separate the headline number.** Report deterministic-grader pass rate and
judge-based pass rate independently. Only the deterministic one is comparable
across time without caveats.

**`ecp trend` gets variance-aware**, flagging regression only when a change
exceeds observed run-to-run noise.

## Compatibility

Additive, except that `llm_judge` results acquire a warning when no model is
pinned. Report and audit schemas gain optional blocks.

## Open questions

- Default `repeat`. `1` keeps CI fast; anything higher multiplies cost. Probably
  `1` by default and required `>1` for benchmark mode.
- How to surface flakiness in exit codes. Does a check passing 4 of 5 fail the
  build? Probably configurable, defaulting to strict.

---

# Phase 4 — Publishable benchmarks

## The problem, and the opportunity

An ECP manifest is already a runnable benchmark: a declarative behaviour
contract whose agent side is framework-agnostic. Someone can publish
`refund-policy@1.0` and **any** agent — CrewAI, PydanticAI, Strands, a raw Node
script — can run it and produce a comparable number.

No framework-coupled eval tool can do that. This is the concrete payoff of
vendor neutrality, and it is worth more than the migration story neutrality is
usually sold on.

## Proposal

A benchmark is a manifest plus its dataset, a pinned judge, a required
`repeat`, and a version — addressed by the manifest digest the audit record
already computes.

```bash
ecp bench run refund-policy@1.0 --target "python agent.py"
```

Output is a **score card** whose provenance is the point:

```json
{
  "benchmark": "refund-policy@1.0",
  "manifest_digest": "sha256:c8a39311...",
  "protocol_version": "1.0",
  "runtime_version": "1.2.0",
  "agent": { "name": "SupportAgent", "capabilities": ["tool_calls", "usage"] },
  "runs": 5,
  "deterministic_score": { "mean": 0.86, "stddev": 0.04 },
  "judge_score": { "mean": 0.79, "stddev": 0.07, "model": "gpt-4o-mini-2024-07-18" },
  "cost": { "total_tokens": 41870, "usd_estimate": 0.31 },
  "latency": { "p95_ms": 812.4 }
}
```

**The registry starts as a git repository of manifests, not a service.** Version
by tag, distribute by URL. A hosted registry can come later if the format proves
itself; building the service first is how this becomes a product nobody uses.

**No leaderboard until reproducibility is demonstrable.** Self-reported scores
without a trusted runner are worthless, and a public leaderboard invites both
gaming and contamination — a published benchmark ends up in training data. If we
ever do a leaderboard, it needs held-out variants and attested runs, which is a
governance problem more than an engineering one.

## Compatibility

Entirely new surface. `ecp bench` is a new command; nothing existing changes.

## Open questions

- Is `usd_estimate` in scope? It requires a pricing table that goes stale and is
  provider-specific. Tokens are objective; dollars are not. Leaning tokens only.
- How do we handle a benchmark whose manifest requires a capability the agent
  lacks — unscoreable, or scored zero? Unscoreable seems honest; zero is what
  people will assume.
- Contamination: do we need a private held-out split from day one, or is that
  premature for a benchmark nobody has heard of yet?

---

## What this roadmap deliberately excludes

- **The proxy / silent interception design.** It is a real adoption idea, but it
  is a workaround for ECP being strictly runtime → agent. Whether the protocol
  should become bidirectional is a phase 1.5 question we should settle before
  building the workaround.
- **Tool mocking.** Depends on the bidirectionality decision above.
- **A TypeScript SDK.** Independently valuable, on its own track, not blocked by
  any of this.

## Sequencing note

Phase 1 is the only one with a closing window. Version negotiation is cheap now
and progressively harder with every agent built against a versionless protocol.
Phases 2 through 4 can be reordered or descoped based on what users ask for.
Phase 1 cannot be deferred without cost.
