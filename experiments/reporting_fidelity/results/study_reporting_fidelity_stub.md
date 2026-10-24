# Study - Reporting fidelity and defect prevalence (`stub` agent)

Generated: 2026-10-24T23:42:27Z

Ground truth comes from instrumented tools that log every real invocation,
independently of what the agent reports through ECP.

## Reporting fidelity

| Metric | Value |
| --- | --- |
| Tool calls actually made and reported | 4 |
| Made but **not** reported | **4** |
| Reported but never made | 0 |
| Recall (reported / actually made) | **0.5** |
| Precision (actually made / reported) | **1.0** |

Recall below 1.0 means ECP is blind to work the agent really did, however
expressive its graders are. Precision below 1.0 means the contract carries
claims the agent did not earn.

Unreported calls produce **false failures**: a `tool_usage` grader asserting a
tool the agent genuinely invoked fails anyway, and the report blames the agent
for an adapter's omission. Compare the last two columns below - any row with no
ground-truth defect but a non-empty flag is one of those.

## Answer accuracy and defect prevalence

- Answer accuracy: **1.0**
- Correct answers: 4
- Of those, trajectory defective: **0** (rate 0.0)

## Per trial

| Scenario | Answer | Actual | Reported | Unreported | Defects (truth) | ECP would flag |
| --- | --- | --- | --- | --- | --- | --- |
| `a100_eligible` | correct | 2 | 1 | check_refund_policy | none | skipped_verification, wrong_argument |
| `b200_too_old` | correct | 2 | 1 | check_refund_policy | none | skipped_verification, wrong_argument |
| `c300_recent` | correct | 2 | 1 | check_refund_policy | none | skipped_verification, wrong_argument |
| `a100_amount` | correct | 2 | 1 | check_refund_policy | none | skipped_verification, wrong_argument |
