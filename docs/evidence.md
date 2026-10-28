# Evidence

What has been measured about ECP, how, and how far the numbers can be trusted. Every figure here comes from a script in [`experiments/`](https://github.com/evaluation-context-protocol/ecp/tree/main/experiments) that can be re-run; the raw per-trial rows are stored next to each summary.

Read the [limitations](#limitations) before quoting any number. The short version: one model (`claude-haiku-5-5`), one small scenario set, and labels written by the ECP author, not by independent annotators.

## What the measurements say

| Question | Finding |
| --- | --- |
| Do outcome-only checks miss real agent mistakes? | Yes. In 9 runs where an agent really issued a refund it had no authority to issue, reply-only judges passed between 5 and 8 of the replies (depending on the tool). `not_called` flagged all 9, in every tool that has such a check. |
| Is ECP a better grader than DeepEval or Promptfoo? | No, and it does not claim to be. On identical cases the LLM-judge results are the same across the three tools, and DeepEval has trajectory checks ECP lacks (allow-lists, ordering). |
| What does ECP do differently? | It refuses to pass a prohibition it cannot verify, and the same manifest drives agents built in different frameworks. See experiments 2 and 3. |
| Does one manifest work across frameworks? | After fixing two adapter bugs the study found, yes: identical verdicts across CrewAI, LangChain, PydanticAI and LlamaIndex, including detecting a real prohibited call. Before the fixes, two of the four crashed. See experiment 3. |

## Experiment 1: natural defects

**Question.** Earlier fault-injection tests plant a defect in a scripted agent, which only shows a grader can catch a defect somebody fabricated. What happens with defects a real model produces?

**Method.** A three-agent CrewAI refund desk ([`examples/crewai_claude_crew`](https://github.com/evaluation-context-protocol/ecp/tree/main/examples/crewai_claude_crew)) on `claude-haiku-5-5`. Its guardrails were removed one at a time, from the full prompt down to a "get things done" instruction with an unwarned `issue_refund` tool (the `eager` variant). Each of 5 variants was run 6 times on 3 customer scenarios: 90 live runs. Ground truth is a log written by the tools themselves, independent of ECP and of the adapter. Each run was graded two ways: an `llm_judge` over the reply alone, and `tool_usage` with `condition: not_called` over the tool calls the adapter reported.

**Result.**

| Variant | Refund really issued |
| --- | --- |
| `guarded` | 0/18 (95% CI 0–18%) |
| `no_writer_rule` | 0/18 |
| `no_tool_warning` | 0/18 |
| `no_review_rule` | 0/18 |
| `eager` | 9/18 (50%, 95% CI 29–71%) |

Of the 9 runs with a real refund, `not_called` flagged 9; ECP's reply-only judge flagged 1 (other judges do somewhat better, see the second pass under experiment 2). In the other 8 the reply said the customer was eligible and that the team would process the refund, wording that gives no sign the refund had already gone out. Neither grader raised a false alarm on the 81 runs without a refund (0/81 each, 95% CI 0–5%).

**What this shows.** Removing prompt rules one at a time did not make the model misbehave; only the explicit "take the action" instruction did. When it did misbehave, the harm was in an action the reply did not report. A grader that reads only the reply cannot see that; a check on the tool call can.

**What it does not show.** Every defect came from a prompt I wrote to cause it, in one model. The reply-only judge's miss is partly about my criterion ("must not claim a refund has been issued"), which the eager replies technically satisfy. A stricter criterion might catch more, but could not know whether the action happened.

## Experiment 2: ECP against other evaluation tools

**Question.** Is anything here better than what exists?

**Method.** The same cases through ECP, DeepEval 4.3.2 and Promptfoo 0.120.19, with every LLM-judged arm using `claude-haiku-5-5` and the same criterion text.

*Reply family:* 28 replies written for this study (15 acceptable, 13 not), each judged three times per tool.

| Tool | Wrongly fails a good reply | Wrongly passes a bad reply | Verdict flips between repeats |
| --- | --- | --- | --- |
| ECP regex (patterns the example used to ship) | 9/15 | 5/13 | 0/28 |
| ECP `llm_judge` | 0/15 | 0/13 | 0/28 |
| DeepEval `GEval` | 0/15 | 0/13 | 0/28 |
| Promptfoo `llm-rubric` | 0/15 | 0/13 | 0/28 |

*Trajectory family:* 9 tool-call trajectories against one policy (look up A100, check its policy, never call `issue_refund`; anything else is allowed).

| Configuration | Correct |
| --- | --- |
| ECP `tool_usage` + `not_called` | 9/9 |
| DeepEval `ToolCorrectnessMetric` + `ToolPermissionMetric` | 9/9 |
| DeepEval `ToolCorrectnessMetric`, exact match | 6/9 (flags a benign extra call, a duplicate and a reordering) |
| Promptfoo `tool-call-f1` (built in) | 7/9 (flags a benign extra call, passes a wrong argument) |
| Promptfoo custom `javascript` assertion | 9/9 (needs hand-written code) |

*A prohibition when the agent reports nothing:*

| Configuration | Agent reports no tool calls |
| --- | --- |
| ECP `not_called`, agent declares `tool_calls` | PASS |
| ECP `not_called`, agent does **not** declare `tool_calls` | **FAIL** ("cannot verify") |
| DeepEval `ToolPermissionMetric` | PASS |
| Promptfoo `javascript` | PASS |

**What this shows.**

- On this corpus the three tools' LLM judges are indistinguishable. Judge grading is not where ECP stands out, and it should not be sold as such.
- The regex graders ECP's example first shipped were bad: they failed 60% of acceptable replies and passed 38% of unacceptable ones. That is why the example now uses a judge.
- For tool-call policy, ECP matches the best configuration of the other tools. DeepEval's metrics are more expressive (allow-lists, ordering).
- A prohibition is satisfied by absence, so it passes vacuously when an agent reports nothing. ECP refuses that case; the other two tools pass it. It is a design choice, with a cost: a manifest asking for `not_called` fails against agents that do not declare `tool_calls`.

**Limits.** The cases are easy; every judge scored 28/28, so the study cannot separate them. DeepEval and Promptfoo were configured by me from their documentation; a maintainer might do better. The judge model is the same family as the model being graded, which a real deployment should avoid.

### Second pass: the 90 saved crew runs from experiment 1

The same 90 runs were then scored by all three tools, each given only what ECP's contract carries: the reply and the tool-call names the adapter reported. Ground truth is the tools' own log (9 runs with a real refund, 81 without).

| Tool | Check | Caught the 9 real refunds | False alarms on 81 clean runs |
| --- | --- | --- | --- |
| ECP | reply judge | 1/9 | 0/81 |
| DeepEval | `GEval` reply judge | 4/9 (2 runs errored on malformed judge JSON) | 0/81 |
| Promptfoo | `llm-rubric` reply judge | 1/9 | 1/81 |
| ECP | `not_called issue_refund` | **9/9** | 0/81 |
| DeepEval | `ToolPermissionMetric` | **9/9** | 0/81 |
| Promptfoo | custom `javascript` prohibition | **9/9** | 0/81 |

Two things follow. First, the finding is not specific to ECP's judge: all three reply judges miss most real refunds (1, 4 and 1 of 9; DeepEval's reads "our team will process the refund" more strictly), and all three tool-call checks catch every one, agreeing on all 90 runs. A check on the action is what sees the failure, in any tool. Second, ECP does not out-judge the others; its value here is carrying the tool calls to the grader in a form every tool can check. DeepEval and Promptfoo were handed ECP's reported tool calls and graded them with their own metrics.

## Experiment 3: one manifest, four frameworks

**Question.** ECP's pitch is that a manifest is written once and the agent behind it can change. Does that hold in practice?

**Method.** The same refund desk, one agent, built four times from the same tools, prompt and model (`claude-haiku-5-5`): CrewAI, LangChain, PydanticAI and LlamaIndex, each using ECP's shipped adapter. Each framework ran in its own virtual environment. The four manifests are generated from one template and the script asserts they differ only in the `target:` line. Each manifest has 11 checks over 3 scenarios (an `llm_judge` on the reply, `tool_usage` for lookup and policy check, and `not_called issue_refund`). As in experiment 1, the tools write their own log, which is compared with what the adapter reported. Two modes were run:

- *Guarded*: the normal prompt. 10 repetitions per framework (120 steps; two overlapping runs were pooled).
- *Eager*: the experiment-1 prompt that makes the agent issue refunds. 5 repetitions per framework (60 steps). This mode exists so that agreement is tested on runs that *should* fail, where "everyone passed" cannot count as agreement.

**Result.**

| | Guarded (should all pass) | Eager (refund really issued in 10 of 15 steps) |
| --- | --- | --- |
| Steps completed, each framework | 30/30 | 15/15 |
| Adapter-reported tool calls vs the tools' own log (recall / precision) | 60/60, 60/60 in every framework | 40/40, 40/40 in every framework |
| `not_called` flagged a refund that really happened | no refunds occurred | 10/10 in every framework |
| `not_called` verdict correct | 30/30 in every framework | 15/15 in every framework |
| Frameworks agreeing on a check's verdict | 110/110 cells | 55/55 cells |

Tool-call sequences were identical across frameworks in every scenario. In eager mode the `llm_judge` also caught the refunds, because this prompt makes the agent say outright that it issued one; that is unlike experiment 1, where the replies hid it.

**Differences the manifest does not hide.**

- No adapter reports `usage`, so token budgets and cost checks cannot be graded on any of the four.
- `evaluation_context` is reported by the CrewAI and LangChain adapters only. A manifest that graded it would fail on PydanticAI and LlamaIndex.
- Agreement here is about verdicts. Wording of replies, step latency and cost differ across frameworks and were not compared.

**Bugs this study found.** The first run, before any change to the SDK, was not portable:

| Framework | As shipped (1 repetition) | After fix |
| --- | --- | --- |
| CrewAI | 3/3 steps ran | unchanged |
| PydanticAI | 3/3 steps ran | unchanged |
| LangChain | 1/3 steps ran; the other two crashed with `public_output must be a string`, because Claude returns a list of content blocks when it writes text beside a tool call | all steps ran |
| LlamaIndex | 0/3 steps ran; every reported tool call had an empty name, because LlamaIndex calls the field `tool_name`, not `name` | all steps ran |

Both fixes are small and have regression tests. Separately, `llama-index-llms-anthropic` 0.12.3 does not work with `anthropic` 2.x, so the LlamaIndex study environment pins `anthropic==0.75.0`.

**What this shows.** After the two fixes, one manifest produced the same verdicts, and the same correct detection of a real prohibited call, across four frameworks. Before them it did not: the shipped adapters had never been run against a real model through these frameworks, so portability held only once a test like this existed.

**Limits.** One agent design, one model, three scenarios. The tool-call sequences were so uniform that the study could not see disagreements about order or count; a more varied agent would test that. Frameworks without ECP adapters, or agents with several sub-agents, were not tried.

## Which of ECP's stated purposes are tested

`why-ecp.md` lists what ECP is for. Against that list:

| Purpose | Tested here? |
| --- | --- |
| Check the agent called the required tool, with the right arguments | Yes (experiments 1, 2, 3) |
| Check policy was followed, beyond what the output shows | Yes, and this is the strongest result (experiments 1 and the second pass) |
| Move an eval between agent frameworks without rewriting it | Yes for four frameworks, after two adapter fixes (experiment 3) |
| Standard fields (`public_output`, `tool_calls`, `evaluation_context`) | Partly: the first two worked everywhere; `evaluation_context` on two of four adapters; `usage` on none |
| Feed results to other evaluation tools | Partly: DeepEval and Promptfoo graded ECP-reported tool calls (second pass). ECP's report format was not imported into a platform |
| Reproducible in CI | Not tested |
| Auditability, enterprise use | Not tested |

## Limitations

- **One model.** Everything ran on `claude-haiku-5-5`, chosen because it is cheap. Results may differ for stronger or weaker models.
- **Small samples.** Intervals are Wilson 95% and are wide. "0/18" means the true rate is plausibly anything up to 18%.
- **Labels are mine.** The 28 replies and 9 trajectories were labelled by the ECP author. They are not independent annotations, and an adversarial reviewer would be right to discount them. A blind labelling sheet is in `experiments/head_to_head/labelling/`; until someone fills it in, treat the reply-family numbers as the author's own.
- **Self-built defects.** The failures come from prompts written to produce them. Nothing here measures how often production agents fail this way.
- **Judge model equals agent model.** The judge and the graded agents are the same model family. Same-family judges can share blind spots.
- **Tool configuration by the author.** The competing tools were set up from their docs, not by their maintainers.
- **Not peer reviewed.** None of this has been independently reproduced.

## Reproducing

Each experiment has its own README-style header in the script; the entry points are:

```bash
python experiments/natural_defects/run_ablation.py          # experiment 1 (about 90 model runs)
python experiments/natural_defects/analyse_ablation.py
python experiments/head_to_head/combine.py                  # experiment 2 summary
python experiments/portability/run_portability.py           # experiment 3
python experiments/portability/analyse_portability.py
```

They need an `ANTHROPIC_API_KEY` and, for experiment 2, Node and a separate DeepEval environment. Runs use the cheapest current model to keep the cost low.
