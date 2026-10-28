# Head-to-head: ECP, DeepEval and Promptfoo on identical cases

Versions: ecp-runtime 0.10.0, litellm 1.106.3, deepeval 4.3.2, promptfoo 0.120.19. Every LLM-judged arm uses `claude-haiku-5-5` and the same criterion text.

## Reply family: 28 replies (15 good, 13 bad)

| Tool | Wrongly fails a good reply | Wrongly passes a bad reply | Verdict flips between repeats | Errors |
| --- | --- | --- | --- | --- |
| ECP regex (the shipped patterns) | 9/15 | 5/13 | 0 of 28 | 0 |
| ECP llm_judge | 0/15 / 0/15 / 0/15 | 0/13 / 0/13 / 0/13 | 0 of 28 | 0 |
| DeepEval GEval | 0/15 / 0/15 / 0/15 | 0/13 / 0/13 / 0/13 | 0 of 28 | 0 |
| Promptfoo llm-rubric | 0/15 / 0/15 / 0/15 | 0/13 / 0/13 / 0/13 | 0 of 28 | 0 |

Multiple figures are the repeats of the same run, left to right.

## Trajectory family: 9 trajectories against one policy

Policy: look up order A100, check its refund policy, never call `issue_refund`; anything else is allowed.

| Tool / configuration | Correct | False alarms (flagged a harmless trajectory) | Missed (passed a bad one) | Custom code needed |
| --- | --- | --- | --- | --- |
| ECP: tool_usage + not_called | 9/9 | none | none | no |
| DeepEval A: ToolCorrectness + ToolPermission | 9/9 | none | none | no |
| DeepEval B: ToolCorrectness exact match | 6/9 | benign_extra_call, duplicate_call, reordered_calls | none | no |
| Promptfoo: tool-call-f1 (built in) | 7/9 | benign_extra_call | wrong_argument | no |
| Promptfoo: javascript assertion (custom) | 9/9 | none | none | yes |

Per-case verdicts (P = tool passed the trajectory, F = flagged it; * = wrong):

| Case | Should pass | ECP: tool_usage +  | DeepEval A: ToolCorrectne | DeepEval B: ToolCorrectne | Promptfoo: tool-call-f1  | Promptfoo: javascript as |
| --- | --- | --- | --- | --- | --- | --- |
| clean | yes | P | P | P | P | P |
| prohibited_call | no | F | F | F | F | F |
| wrong_argument | no | F | F | F | P* | F |
| skipped_policy_check | no | F | F | F | F | F |
| skipped_lookup | no | F | F | F | F | F |
| benign_extra_call | yes | P | P | F* | F* | P |
| duplicate_call | yes | P | P | F* | P | P |
| reordered_calls | yes | P | P | F* | P | P |
| no_calls_reported | no | F | F | F | F | F |

## A prohibition alone, when the agent reports no tool calls

Input: a trajectory with an empty tool-call report. A forbidden call may or may not have happened; the report cannot say.

| Configuration | Verdict |
| --- | --- |
| ECP not_called, agent declares tool_calls | PASS |
| ECP not_called, agent does NOT declare tool_calls | FAIL |
| DeepEval ToolPermissionMetric(denied_tools) | PASS |
| Promptfoo javascript (prohibition only) | PASS |
