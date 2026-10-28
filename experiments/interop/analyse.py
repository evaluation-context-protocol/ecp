"""
Three evaluators x four agent frameworks, through one protocol -> results/interop.md

Evaluators: `ecp run` (rows from the portability study), Promptfoo via the ECP provider,
DeepEval via the ECP bridge. For each evaluator and framework: did every step complete,
did the tool calls the evaluator received match what the tools really did, and was the
"never call issue_refund" verdict right?
"""

import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = HERE.parent / "portability" / "results"
FRAMEWORKS = ("crewai", "langchain", "pydanticai", "llamaindex")
EVALUATORS = ("ecp run", "Promptfoo", "DeepEval")


def jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def from_ecp(path, mode):
    out = []
    for r in jsonl(path):
        nc = next((c for c in r["checks"] if "not called" in c.get("reasoning", "") or "Forbidden" in c.get("reasoning", "")), None)
        judge = next((c for c in r["checks"] if c["type"] == "llm_judge"), None)
        out.append({"evaluator": "ecp run", "framework": r["framework"], "mode": mode, "scenario": r["scenario"],
                    "error": r["error"] if r["status"] != "ok" else None,
                    "reported_tools": r["reported_tools"], "actual_tools": r["actual_tools"],
                    "not_called_pass": nc["passed"] if nc else None, "reply_pass": judge["passed"] if judge else None})
    return out


rows = from_ecp(PORT / "portability_rows.jsonl", "guarded") + from_ecp(PORT / "portability_rows_eager.jsonl", "eager")
for r in jsonl(HERE / "results" / "promptfoo_rows.jsonl"):
    rows.append(dict(r, evaluator="Promptfoo"))
for fw in FRAMEWORKS:
    for r in jsonl(HERE / "results" / f"deepeval_rows_{fw}.jsonl"):
        rows.append(dict(r, evaluator="DeepEval"))

cell = defaultdict(lambda: {"steps": 0, "done": 0, "match": 0, "issued": 0, "caught": 0, "nc_right": 0, "nc_n": 0})
for r in rows:
    c = cell[(r["evaluator"], r["framework"])]
    c["steps"] += 1
    if r.get("error") or r.get("reported_tools") is None:
        continue
    c["done"] += 1
    c["match"] += sorted(r["reported_tools"]) == sorted(r["actual_tools"])
    real = "issue_refund" in r["actual_tools"]
    if r.get("not_called_pass") is not None:
        c["nc_n"] += 1
        c["nc_right"] += (not r["not_called_pass"]) == real
        c["issued"] += real
        c["caught"] += real and not r["not_called_pass"]

out = ["# Interop: three evaluators, four agent frameworks, one protocol", "",
       "Each evaluator used one configuration for all four frameworks; only the agent's `target` changed. "
       "Ground truth is the log the agents' tools write themselves.", "",
       "| Evaluator | Framework | Steps completed | Tool calls received = tool calls made | Real refunds caught by \"never call issue_refund\" | That verdict correct |",
       "|---|---|---|---|---|---|"]
tot = defaultdict(int)
for ev in EVALUATORS:
    for fw in FRAMEWORKS:
        c = cell[(ev, fw)]
        out.append(f"| {ev} | {fw} | {c['done']}/{c['steps']} | {c['match']}/{c['done']} | {c['caught']}/{c['issued']} | {c['nc_right']}/{c['nc_n']} |")
        for k, v in c.items():
            tot[k] += v
out += ["", f"**Total:** {tot['done']}/{tot['steps']} steps completed; tool calls matched ground truth in {tot['match']}/{tot['done']}; "
        f"{tot['caught']}/{tot['issued']} real refunds caught; prohibition verdict correct in {tot['nc_right']}/{tot['nc_n']}.", ""]

out += ["## Reply judges (for reference; each evaluator uses its own judge)", "",
        "| Evaluator | Guarded runs: reply passed | Eager runs: reply passed |", "|---|---|---|"]
for ev in EVALUATORS:
    cols = []
    for mode in ("guarded", "eager"):
        v = [r["reply_pass"] for r in rows if r["evaluator"] == ev and r["mode"] == mode and r.get("reply_pass") is not None]
        cols.append(f"{sum(v)}/{len(v)}")
    out.append(f"| {ev} | " + " | ".join(cols) + " |")

errs = [r for r in rows if r.get("error") or r.get("metric_errors")]
out += ["", f"Errors: {len(errs)}"] + [f"- {r['evaluator']} / {r['framework']} / {r['scenario']}: {(r.get('error') or r.get('metric_errors'))}"[:200] for r in errs]
(HERE / "results" / "interop.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
