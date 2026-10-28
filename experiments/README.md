# Experiments

The studies behind the claims ECP makes. ECP is a protocol between agents and the tools that evaluate them, so the claims are about that position:

1. **Any evaluator can test any agent through ECP**, with no framework-specific code.
2. **One evaluation definition works across agent frameworks.**
3. **The contract has to carry what the agent did** (tool calls), not only what it said.

ECP does not claim to grade better than evaluation frameworks such as DeepEval or Promptfoo. It sits underneath them.

Every number below comes from a script in this folder and the raw per-run rows are next to it. All runs used `claude-haiku-5-5`, the cheapest current model; see [Limitations](#limitations).

## 1. Interop: three evaluators x four agent frameworks — [`interop/`](interop/)

One refund agent, built four times (CrewAI, LangChain, PydanticAI, LlamaIndex) from the same tools, prompt and model, each on ECP's shipped adapter. Three evaluators tested it:

- `ecp run`, ECP's reference runtime, with one manifest;
- **Promptfoo**, through the ECP provider ([`integrations/promptfoo`](../integrations/promptfoo/)), with one config;
- **DeepEval**, through the ECP bridge (`ecp_runtime.integrations.deepeval`), with one script and DeepEval's own metrics (`GEval`, `ToolCorrectnessMetric`, `ToolPermissionMetric`).

For each evaluator, the configuration was identical for all four frameworks except the agent's `target`. Runs used the normal prompt and an "eager" prompt that makes the agent issue refunds it is not allowed to, so the evaluators were tested on runs that should fail. Ground truth is a log the agents' tools write themselves.

| | Result |
| --- | --- |
| Steps completed | 276 / 276 |
| Tool calls the evaluator received = tool calls the agent made | 276 / 276 |
| Real unauthorised refunds caught by "never call `issue_refund`" | 72 / 72 (every evaluator, every framework) |
| That verdict correct, including no false alarms | 276 / 276 |

Per evaluator and framework: [`interop/results/interop.md`](interop/results/interop.md).

**What this shows.** Promptfoo and DeepEval tested agents in four frameworks without a line of framework code, and got the same, correct answer about what each agent did as ECP's own runtime. That is the protocol doing its job on both sides.

**What it does not show.** One agent design with three scenarios; 2 repetitions per mode for Promptfoo and DeepEval (5 to 10 for `ecp run`). Tool-call order and count were identical across frameworks, so disagreement on those was never tested.

## 2. Agent-framework portability — [`portability/`](portability/)

The same manifest, generated from one template and asserted to differ only in `target:`, run through `ecp run` on all four frameworks. This is the `ecp run` row of the interop table, plus what the study found on the way:

- **The shipped adapters were not portable at first.** LangChain crashed on 2 of 3 steps (Anthropic returns a list of content blocks; the adapter passed it on as the reply). LlamaIndex crashed on every step (it names the tool `tool_name`, which the adapter did not read). Both were fixed, with regression tests; after the fixes every step ran.
- **Optional fields are uneven.** No adapter reports `usage`. Only CrewAI and LangChain report `evaluation_context`. A check on either would not be portable today.
- `llama-index-llms-anthropic` 0.12.3 does not work with `anthropic` 2.x; the study pins `anthropic==0.75.0` for LlamaIndex.

Summaries: [`portability/results/`](portability/results/).

## 3. Why the contract carries tool calls — [`natural_defects/`](natural_defects/)

A three-agent CrewAI refund desk, with its guardrails removed one at a time, run 90 times. Removing rules did not make the model misbehave; only an "eager" prompt ("resolve the problem completely, using your tools") did, issuing a refund in 9 of 18 runs. Each run was then graded by all three tools, given the reply and the reported tool calls ([`natural_defects/crosscheck/`](natural_defects/crosscheck/)):

| Check | Real refunds caught (of 9) | False alarms (of 81) |
| --- | --- | --- |
| Reply judge: ECP / DeepEval / Promptfoo | 1 / 4 / 1 | 0 / 0 / 1 |
| Tool-call prohibition: ECP / DeepEval / Promptfoo | 9 / 9 / 9 | 0 / 0 / 0 |

The replies said things like "our team will process the refund", which gives no sign it had already gone out. Every tool's reply judge missed most of them; every tool's check on the tool calls caught all of them. This is not a point about ECP's grader. It is why an evaluation contract needs `tool_calls`, and why ECP will not pass "never called X" for an agent that does not report its tool calls.

## 4. Same cases through each tool — [`head_to_head/`](head_to_head/)

28 replies and 9 tool-call trajectories scored by ECP's graders, DeepEval and Promptfoo. This is a consistency check on the corpus, not a ranking: the LLM judges agreed on all 28 replies, and DeepEval's tool metrics are more expressive than ECP's (allow-lists, ordering). Two findings matter for ECP:

- The regex checks ECP's example first shipped failed 9 of 15 good replies and passed 5 of 13 bad ones. The example now uses a judge.
- On an agent that reports no tool calls, DeepEval's `ToolPermissionMetric` and a Promptfoo assertion both pass "never call X". ECP fails it unless the agent declared the `tool_calls` capability, and the DeepEval bridge refuses such agents for the same reason.

**Labels.** The 28 replies were labelled by the author, then blind by a second person ([`head_to_head/labelling/`](head_to_head/labelling/)): 24 of 28 agree, Cohen's kappa 0.72. All four disagreements are replies the written criterion allows ("passed to our team for review") that the second labeller judged by a stricter standard. The second labeller is the project owner, so not independent.

## Limitations

- **One model** (`claude-haiku-5-5`), for agents and judges alike. Same-family judges can share blind spots.
- **Small samples.** Intervals are wide; "0 of 81" is consistent with a true rate up to about 5%.
- **One agent design**, three scenarios. Multi-agent systems were tried only with CrewAI (study 3).
- **Self-made failures.** The refunds came from a prompt written to cause them; nothing here measures how often production agents fail this way.
- **Tool configuration by the author.** DeepEval and Promptfoo were set up from their documentation, not by their maintainers.
- **Not tested:** ECP report import into hosted evaluation platforms, CI behaviour, and non-Python agents.

## Reproducing

Each study needs an `ANTHROPIC_API_KEY` (read from `examples/crewai_claude_crew/.env`). The frameworks need separate virtual environments, and DeepEval needs its own because it pins an older `click` than current `litellm` does; locations are in `portability/make_manifests.py`.

```bash
python experiments/interop/scenarios.py                       # writes scenarios.json (machine-specific paths)
python experiments/interop/drive_promptfoo.py --reps 2
python experiments/interop/drive_deepeval.py --framework crewai --reps 2   # per framework, in the DeepEval env
python experiments/portability/run_portability.py --reps 5     # the `ecp run` arm
ECP_PORTABILITY_MODE=eager python experiments/portability/run_portability.py --reps 5
python experiments/interop/analyse.py
```
