# Changelog

## Unreleased

### Added

- Added `ecp_runtime.session.ECPSession`, a client for evaluators other than `ecp run`: start an ECP agent (stdio command or HTTP URL), initialize it, send steps, and get back the reply, tool calls and evaluation context, validated the way the runner validates them.
- Added a Promptfoo provider (`integrations/promptfoo/ecp_provider.py`): Promptfoo can test any ECP agent, with the reply as `output` and tool calls in the response `metadata`.
- Added a DeepEval bridge (`ecp_runtime.integrations.deepeval`) that turns ECP steps into `LLMTestCase` objects. It refuses agents that have not declared `tool_calls`, since DeepEval would read their empty tool list as "no tools used". DeepEval is imported only when the bridge is used.
- Added `condition: not_called` on `tool_usage`, a prohibition on a tool call: `tool_name: issue_refund` fails if the agent called it, and `arguments` narrows the ban to calls matching those pairs. Until now ECP could only assert a call was *present*, so an agent could take an unauthorised action, write a clean reply, and pass every grader.
- `called` is accepted as an explicit spelling of the existing default `tool_usage` behaviour.

### Changed

- A `not_called` grader **fails rather than passes** when the agent has not declared the `tool_calls` capability. A prohibition passes when the call is absent, so an agent or adapter that drops tool calls would otherwise satisfy it vacuously. The failure message explains how to declare the capability. Presence checks are unaffected, since they already fail safe.
- `evaluate_step` takes an optional `declared_capabilities` argument. The runner always supplies it; direct callers that omit it get the previous lenient behaviour.

### Fixed

- **`llm_judge` verdicts could be forged by the text being judged.** The verdict was decided by `"RESULT: PASS" in response`, a substring test over the whole response. A judge explaining a failure quotes the offending text, so an agent reply containing the words `RESULT: PASS` produced a response that quoted them while concluding `RESULT: FAIL`, and was passed anyway. The model was not fooled; the parser was. The verdict is now read only from the end of the response, and a response with no trailing verdict is a failed grade reported as a judge error.
- `llm_judge` always sent `temperature=0`, which current Claude models reject (`does not support temperature=0.0. Only temperature=1 is supported`), so every judge call against them failed. litellm is now asked to drop parameters a model will not take.
- The "judge unavailable" message told users whose litellm was installed but failed to import to run `pip install 'ecp-runtime[judge]'`, which changes nothing. It now distinguishes "not installed" from "installed but failed to import" and gives advice matching the cause.
- **The LangChain adapter crashed when a model returned a list of content blocks.** Anthropic models return text and tool-use as separate blocks, so `public_output` became a list and the step failed with `public_output must be a string`. Text blocks are now joined and tool-use blocks ignored. Found by running one manifest across four frameworks against a real model.
- **The LlamaIndex adapter reported tool calls with an empty name.** LlamaIndex's `ToolCallResult` names the tool `tool_name` and its arguments `tool_kwargs`, which the adapter did not read, so every step with a tool call failed validation. Both are now read.

## 0.10.0

Protocol version negotiation, auditable run telemetry, and a lighter install.

> Versions `0.4.0`-`0.9.0` were tagged and published without changelog entries.
> Their changes are consolidated here rather than reconstructed per-version.

### Added

- Added agent capability declaration. `@agent(name=..., capabilities={...})` tells the runtime what an agent can report (`tool_calls`, `evaluation_context`, `usage`, `reset`, `multi_turn`), and the runtime derives what a manifest needs from its graders. A capability a manifest needs but the agent does not declare warns by default, naming the grader that asked for it. (#26)
- Added `require_capabilities: true` as a manifest option, turning that warning into a failure before any step runs.
- Added JSON-RPC error `-32002` (`CAPABILITY_REQUIRED`).
- Added `MAJOR.MINOR` protocol version negotiation to `agent/initialize`, independent of package versions.
- Added initialize request/result schemas and recorded the negotiated protocol version in audit metadata.
- Added a run-level wall-clock budget via `--max-duration` / `ECP_MAX_DURATION`, separate from the existing per-RPC `--timeout`.
- Added a structured audit record covering run id, timestamps, manifest SHA-256 digest, agent metadata, configured limits, per-step latency and `exit_reason`, token usage, and pass/fail totals. Embedded under `audit` in the JSON report and writable standalone with `ecp run --audit-out`.
- Added `schema/audit.schema.json` and referenced it from `report.schema.json`.
- Added an optional `usage` field to the `agent/step` result (`input_tokens`, `output_tokens`, `total_tokens`) with SDK and conformance validation, aggregated into the audit record.
- Added typed execution errors (`ecp_runtime.errors`) so failures are classified rather than pattern matched on message text.
- Added spec sections for execution boundaries and the audit record.
- Added an adapter conformance harness (`ecp.testing`): `record_fixture` captures a real framework exchange, `replay` re-runs an adapter against it with no framework install and no API key. Adapter breakage now fails in CI instead of surfacing to users as empty `tool_calls`.
- Added a nightly workflow that runs the real framework demos against live models, covering the framework drift that replayed fixtures cannot.

### Fixed

- `ecp conformance` no longer reports a clean pass for `agent/reset` against an agent with no reset hook. The SDK now infers the `reset` capability from whether `@on_reset` is registered rather than claiming it unconditionally, and the conformance report says when the call is likely a no-op. Note the runner never calls `agent/reset` — scenario isolation comes from spawning a fresh agent per scenario — so this affected `ecp conformance`, the Inspector, and the pytest fixture rather than run isolation. (#27)

### Changed

- Versionless agents remain supported as legacy protocol `0.1` with one warning per run; incompatible major versions stop execution with `VERSION_UNSUPPORTED` (`-32001`).
- **Breaking (install):** `litellm` moved from a required dependency to the optional `judge` extra. `pip install ecp-runtime` no longer pulls it in; the `llm_judge` grader now needs `pip install "ecp-runtime[judge]"`. The base install is substantially lighter and the pin is no longer imposed on users who never use a judge.
- `graders.py` now tolerates *any* exception while importing litellm, not just `ImportError`. A broken or partially-installed optional dependency no longer takes the whole runtime down, and the reason is reported in the grader message instead of being swallowed.
- **Breaking (runtime behavior):** a timeout, crash, protocol violation, or JSON-RPC error no longer aborts the whole run. The failing step is recorded as failed, remaining steps in that scenario are marked skipped, and the next scenario proceeds with a fresh agent. Previously one hung agent killed the run and produced no report at all.
- Steps that never produced a result now contribute a failed `execution` check, so a timed-out step can no longer be counted as a pass by CI.
- `ECPRunner.run_scenarios()` returns two new keys, `exit_reason` and `audit`. Existing `passed` / `total` / `scenarios` keys are unchanged.
- HTTP transport read timeouts are now classified as timeouts rather than generic transport errors.
- The PydanticAI adapter reports token counts through the structured `usage` field instead of stringifying them into `evaluation_context`, so they aggregate into the audit record and no longer pollute graded text.

### Fixed

- Fixed the project to build, test, and document cleanly on macOS, and extended the test matrix to cover it.

## 0.3.1

This release makes ECP easier to share with developers as a usable portable evaluation contract.

### Added

- Added `evaluation_context` as the preferred evaluator-safe audit field.
- Added backward compatibility for the deprecated `private_thought` field.
- Added `ecp init`, `ecp validate`, `ecp doctor`, and `ecp conformance`.
- Added JSON Schemas for manifests, agent results, tool calls, and reports.
- Added a realistic customer support refund-policy demo.
- Added CI documentation and a "Why ECP?" positioning page.
- Added contributor guidance.

### Changed

- Updated docs, README, package READMEs, and PyPI-facing package descriptions to position ECP as a vendor-neutral portable eval contract.
- Updated examples and adapters to prefer `evaluation_context`.
- Updated JSON and HTML reports to include `evaluation_context` and `tool_calls`.
- Updated tool usage check results to report against `tool_calls`.

### Notes

- `0.3.0` was already tagged, so this release uses `0.3.1` for the public package update.
- New agents should use `evaluation_context`; `private_thought` remains accepted for compatibility.
