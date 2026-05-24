# Changelog

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
