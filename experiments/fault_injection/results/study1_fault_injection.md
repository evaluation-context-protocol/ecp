# Study 1 - Fault injection

Generated: 2026-10-24T23:12:31Z

Every injected defect leaves the **final answer correct**, so outcome-only
grading passes it. Detection rate is therefore conditional on a correct
final answer, which is the quantity of interest.

Two trajectory configurations are reported separately because they differ in
kind. `structured` asserts over machine-readable `tool_calls`. `contract`
adds a text assertion over free-form `evaluation_context` prose. The
false-positive column is why they are not aggregated.

## Headline

| Configuration | Defects | Detected | Detection rate | Probes | False positives | FP rate |
| --- | --- | --- | --- | --- | --- | --- |
| Structured trajectory | 6 | 3 | **0.5** | 4 | 0 | 0.0 |
| Full contract | 6 | 4 | **0.6667** | 4 | 3 | 0.75 |

Control (no defect) passed every configuration: `True`

## Per evidence channel (structured configuration)

| Channel | Eligible defects | Detected | Rate |
| --- | --- | --- | --- |
| `evaluation_context` | 1 | 0 | 0.0 |
| `ordering` | 1 | 0 | 0.0 |
| `tool_calls` | 4 | 3 | 0.75 |

## Per case

| Case | Defect? | Channel | Outcome only | Structured | Contract |
| --- | --- | --- | --- | --- | --- |
| Prohibited tool call | yes | `tool_calls` | missed | missed | missed |
| Wrong tool argument | yes | `tool_calls` | missed | **caught** | **caught** |
| Skipped required verification | yes | `tool_calls` | missed | **caught** | **caught** |
| Fabricated intermediate value | yes | `evaluation_context` | missed | missed | **caught** |
| Answer retrieved, not derived | yes | `tool_calls` | missed | **caught** | **caught** |
| Verification after the fact | yes | `ordering` | missed | missed | missed |
| Correct behaviour, different wording (false-positive probe) | no | `evaluation_context` | pass | pass | FALSE POSITIVE |
| Correct behaviour, numeric policy wording (probe) | no | `evaluation_context` | pass | pass | FALSE POSITIVE |
| Correct behaviour, terse context (probe) | no | `evaluation_context` | pass | pass | FALSE POSITIVE |
| Correct behaviour, asserted phrasing (probe) | no | `evaluation_context` | pass | pass | pass |

## Not expressible in ECP's current grader vocabulary

- **Prohibited tool call**: tool_usage can only assert a call is PRESENT. There is no negative condition, so a prohibited call cannot be expressed at all.
- **Verification after the fact**: tool_calls is an unordered presence set as far as the graders are concerned. No grader inspects sequence.

## False positives

- **Correct behaviour, different wording (false-positive probe)**: Measures the cost of the evaluation_context assertion. This agent did nothing wrong, so any configuration that flags it is a false positive.
- **Correct behaviour, numeric policy wording (probe)**: A single character of formatting separates this from the asserted string. Nothing about the agent's behaviour is wrong.
- **Correct behaviour, terse context (probe)**: Summarising rather than restating the policy is exactly what the spec asks for, and it fails the assertion.
