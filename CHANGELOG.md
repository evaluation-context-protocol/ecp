# Changelog

## 0.4.1

This patch release synchronizes the public installation documentation with the
current package line.

### Changed

- Updated repository, SDK, runtime, quickstart, and CI installation examples.
- Clarified that Streamable HTTP agents and their clients run in separate terminals.

## 0.4.0

This release establishes a stricter, backward-compatible protocol contract and adds
first-class support for async Python agents.

### Added

- Added method-specific conformance validation for initialize, step, and reset responses.
- Added machine-readable conformance reports with `--json` and `--json-out`.
- Added synchronous and asynchronous `@on_step` and `@on_reset` support across stdio
  and Streamable HTTP.
- Added configurable RPC timeouts through `--timeout` and `ECP_RPC_TIMEOUT`.
- Added a runnable async Python example covering both supported transports.
- Expanded automated test coverage across Python 3.9 through 3.13.

### Changed

- Aligned runtime models, SDK result normalization, JSON Schemas, and protocol validation.
- Enforced JSON-RPC response identifier matching and preserved evaluator-visible logs.
- Improved timeout and RPC failure diagnostics with method, scenario, and step context.

### Compatibility

- Existing valid synchronous agents remain supported without migration.
- Invalid manifests and malformed protocol payloads that previously passed through are
  now rejected with actionable diagnostics.

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
