# Changelog

## Unreleased

Execution boundaries and auditable run telemetry.

### Added

- Added a run-level wall-clock budget via `--max-duration` / `ECP_MAX_DURATION`, separate from the existing per-RPC `--timeout`.
- Added a structured audit record covering run id, timestamps, manifest SHA-256 digest, agent metadata, configured limits, per-step latency and `exit_reason`, token usage, and pass/fail totals. Embedded under `audit` in the JSON report and writable standalone with `ecp run --audit-out`.
- Added `schema/audit.schema.json` and referenced it from `report.schema.json`.
- Added an optional `usage` field to the `agent/step` result (`input_tokens`, `output_tokens`, `total_tokens`) with SDK and conformance validation, aggregated into the audit record.
- Added typed execution errors (`ecp_runtime.errors`) so failures are classified rather than pattern matched on message text.
- Added spec sections for execution boundaries and the audit record.

### Changed

- **Breaking (runtime behavior):** a timeout, crash, protocol violation, or JSON-RPC error no longer aborts the whole run. The failing step is recorded as failed, remaining steps in that scenario are marked skipped, and the next scenario proceeds with a fresh agent. Previously one hung agent killed the run and produced no report at all.
- Steps that never produced a result now contribute a failed `execution` check, so a timed-out step can no longer be counted as a pass by CI.
- `ECPRunner.run_scenarios()` returns two new keys, `exit_reason` and `audit`. Existing `passed` / `total` / `scenarios` keys are unchanged.
- HTTP transport read timeouts are now classified as timeouts rather than generic transport errors.

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
