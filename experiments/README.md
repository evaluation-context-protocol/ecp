# ECP experiments

Reproducible studies backing the ECP paper. Each is a script, not a notebook, and
each writes machine-readable results alongside a rendered report.

```bash
python experiments/fault_injection/run_study.py
```

No API keys and no framework installs are required for Study 1. That is
deliberate: the quantity being measured is what the *contract* can express, and
mixing in model nondeterminism would make the number unreproducible without
telling us anything extra about the protocol.

---

## Study 1 - Fault injection (done)

**Question.** Among trajectory defects that leave the final answer correct, what
fraction does trajectory grading catch that outcome-only grading misses?

**Method.** A taxonomy of seven trajectory defects plus four non-defect probes.
Each becomes a real ECP agent, driven through the real `ecp` CLI under three
grading configurations: outcome only, outcome plus structured `tool_calls`
assertions, and that plus a text assertion on `evaluation_context`. A defect
counts as detected only when outcome grading passes it and a trajectory
configuration fails it.

Every case carries a prediction of which configurations should flag it. The
script asserts prediction against measurement and exits non-zero on
disagreement, so the reported numbers cannot drift from the taxonomy's claims.
That check has already caught one methodological error in this study's own
design (see *Threats* below).

**Results.** See [`fault_injection/results/study1_fault_injection.md`](fault_injection/results/study1_fault_injection.md).

| Configuration | Detection rate | False-positive rate |
| --- | --- | --- |
| Structured trajectory (`tool_calls`) | **0.50** | **0.00** |
| Full contract (adds `evaluation_context` text) | **0.67** | **0.75** |

Three findings worth stating plainly:

1. **Structured tool-call evidence catches half the defects outcome grading
   misses, with no false positives.** That is the defensible core of the
   contribution.
2. **The `evaluation_context` text assertion is net-harmful as a detector.** It
   raises detection by one case and falsely flags three of four correct agents,
   because a `text_match` over free-form prose fires on benign rephrasing. The
   spec asks agents to *summarise* evidence; summaries vary, and the assertion
   cannot tell variation from fabrication.
3. **Two defect classes are not expressible at all.** A prohibited tool call
   cannot be asserted because `tool_usage` has no negative condition, and
   out-of-order verification cannot be asserted because no grader inspects
   sequence. Both are the policy-enforcement cases ECP's positioning leans on
   hardest.

**Threats to validity.** Stated because they bound the claim:

- *Synthetic agents.* Trajectories are fixed rather than produced by a model.
  This measures grader expressiveness, not real-world defect prevalence. It
  cannot tell you how often these defects occur.
- *Small n.* Six eligible defects and four probes. The rates are illustrative of
  mechanism, not estimates of population frequency.
- *Assertion authorship.* The `evaluation_context` assertion was written from the
  domain (a 30-day policy), not from knowledge of the defects. An earlier
  revision wrote it from the defect, which made `fabricated_value` look
  detectable when the detector was tautological. The prediction check caught it.
- *Single domain.* One refund-agent scenario.

---

## Study 2 - Cross-framework agreement (designed, not run)

**Question.** Run one manifest against functionally equivalent agents in
CrewAI, LangChain, LlamaIndex and PydanticAI. Do the four produce the same
verdict?

The portability claim is currently true by construction - adapters exist because
we wrote them. Measuring agreement tests it, and disagreements are the
interesting data, because they show where frameworks expose evidence unevenly.

**Two variants, and the cheaper one is better science:**

- *Replay variant (no keys needed).* The adapter conformance fixtures in
  `sdk/python/tests/fixtures/adapters/` already record one equivalent exchange
  per framework. Running identical graders against all four adapter outputs
  measures adapter-level agreement with model nondeterminism removed. We already
  know from those fixtures that `evaluation_context` differs sharply across
  adapters while `tool_calls` agrees, so this variant has a result waiting in it.
- *Live variant (needs four installs and API keys).* Adds real model
  nondeterminism, which requires repeated runs and variance reporting to be
  meaningful. Strictly more realistic and strictly noisier.

Do the replay variant first. It isolates the adapter layer, which is the thing
the portability claim is actually about.

---

## Study 3 - Overhead (designed, not run)

**Question.** What does the contract cost in latency and tokens?

One expectation to set before measuring: **ECP adds no prompt tokens.** It reads
`tool_calls` and `evaluation_context` the agent already produced; it does not
inject instructions. Any token delta comes from an agent choosing to generate a
richer `evaluation_context`, which is an authoring decision rather than a
protocol cost. Reporting "token overhead" without that distinction would
overstate the cost.

The real overhead is latency, and it is dominated by **process spawn**, since the
runtime starts a fresh agent per scenario. That is measurable now from the audit
record's `latency` block and per-step `duration_ms`, comparing a direct in-process
call against the same agent driven over stdio and over Streamable HTTP.
