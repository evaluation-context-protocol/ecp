"""
Merge ECP, DeepEval and Promptfoo results into one scored comparison.

Reads results/{cases,ecp,ecp_prohibition,deepeval,promptfoo_reply,promptfoo_traj}.json
and writes results/head_to_head.md and results/head_to_head.json. Standard library only.
"""

import json
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"


def load(name):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


cases = load("cases.json")
ecp = load("ecp.json")
ecp_pro = load("ecp_prohibition.json")
dee = load("deepeval.json")
pf_reply = load("promptfoo_reply.json")["results"]["results"]
pf_traj = load("promptfoo_traj.json")["results"]["results"]

REPLY = cases["reply_cases"]
TRAJ = cases["traj_cases"]
GOOD = [c["id"] for c in REPLY if c["label"] == "good"]
BAD = [c["id"] for c in REPLY if c["label"] == "bad"]


# ---------------------------------------------------------------- reply family
def promptfoo_reply_runs():
    """Group Promptfoo's repeated results by case id -> list of pass booleans."""
    by_id = defaultdict(list)
    errors = 0
    for r in pf_reply:
        meta = (r.get("testCase") or {}).get("metadata") or {}
        grading = r.get("gradingResult") or {}
        reason = str(grading.get("reason", ""))
        # Promptfoo copies the judge's reasoning into `.error` for an ordinary failed
        # assertion (failureReason 1), so `.error` alone cannot mean "the call failed".
        # An earlier version of this treated every failed verdict as an API error and
        # dropped it from the tallies, which made Promptfoo look flawless. Real errors
        # carry failureReason 2, or a grader message beginning "API call error".
        if r.get("failureReason") == 2 or reason.startswith("API call error"):
            errors += 1
            by_id[meta["id"]].append(None)
        else:
            by_id[meta["id"]].append(bool(r.get("success")))
    repeats = max(len(v) for v in by_id.values())
    return [[by_id[c["id"]][k] for c in REPLY] for k in range(repeats)], errors


pf_runs, pf_errors = promptfoo_reply_runs()
reply_arms = {
    "ECP regex (the shipped patterns)": [ecp["reply"]["regex"]],
    "ECP llm_judge": ecp["reply"]["judge"],
    "DeepEval GEval": [[v["pass"] for v in batch] for batch in dee["reply"]["geval"]],
    "Promptfoo llm-rubric": pf_runs,
}


def reply_stats(runs):
    per_run = []
    for run in runs:
        ff = sum(1 for i in GOOD if run[i] is False)
        miss = sum(1 for i in BAD if run[i] is True)
        err = sum(1 for v in run if v is None)
        per_run.append((ff, miss, err))
    flips = sum(1 for i in range(len(REPLY)) if len({run[i] for run in runs}) > 1) if len(runs) > 1 else 0
    return per_run, flips


def fmt_runs(per_run, idx, denom):
    vals = [r[idx] for r in per_run]
    return " / ".join(f"{v}/{denom}" for v in vals)


reply_table = []
for arm, runs in reply_arms.items():
    per_run, flips = reply_stats(runs)
    reply_table.append(
        {
            "arm": arm,
            "false_fail_per_run": [r[0] for r in per_run],
            "miss_per_run": [r[1] for r in per_run],
            "errors": sum(r[2] for r in per_run),
            "flips": flips,
            "repeats": len(runs),
        }
    )


def wrong_cases(runs):
    """Case ids a tool got wrong in any repeat, with the direction."""
    out = []
    for i, c in enumerate(REPLY):
        verdicts = [run[i] for run in runs]
        if c["label"] == "good" and any(v is False for v in verdicts):
            out.append((i, "wrongly failed a good reply", verdicts))
        if c["label"] == "bad" and any(v is True for v in verdicts):
            out.append((i, "wrongly passed a bad reply", verdicts))
    return out


# ------------------------------------------------------------ trajectory family
def pf_traj_verdicts():
    out = defaultdict(dict)
    for r in pf_traj:
        meta = (r.get("testCase") or {}).get("metadata") or {}
        out[meta["variant"]][meta["id"]] = bool(r.get("success"))
    return out


pf_t = pf_traj_verdicts()
traj_arms = {
    "ECP: tool_usage + not_called": {cid: v["pass"] for cid, v in ecp["traj"].items()},
    "DeepEval A: ToolCorrectness + ToolPermission": {cid: v["A"] for cid, v in dee["traj"].items()},
    "DeepEval B: ToolCorrectness exact match": {cid: v["B"] for cid, v in dee["traj"].items()},
    "Promptfoo: tool-call-f1 (built in)": pf_t["builtin"],
    "Promptfoo: javascript assertion (custom)": pf_t["custom"],
}
needs_code = {
    "ECP: tool_usage + not_called": "no",
    "DeepEval A: ToolCorrectness + ToolPermission": "no",
    "DeepEval B: ToolCorrectness exact match": "no",
    "Promptfoo: tool-call-f1 (built in)": "no",
    "Promptfoo: javascript assertion (custom)": "yes",
}
expect = {c["id"]: c["expect_pass"] for c in TRAJ}
traj_table = []
for arm, verdicts in traj_arms.items():
    correct = sum(1 for cid, v in verdicts.items() if v == expect[cid])
    false_alarm = [cid for cid, v in verdicts.items() if expect[cid] and not v]
    missed = [cid for cid, v in verdicts.items() if not expect[cid] and v]
    traj_table.append(
        {"arm": arm, "correct": correct, "total": len(expect), "false_alarms": false_alarm,
         "missed": missed, "custom_code": needs_code[arm]}
    )

# --------------------------------------------------- prohibition alone, empty report
prohibition = {
    "ECP not_called, agent declares tool_calls": ecp_pro["no_calls_reported"]["declared"],
    "ECP not_called, agent does NOT declare tool_calls": ecp_pro["no_calls_reported"]["undeclared"],
    "DeepEval ToolPermissionMetric(denied_tools)": dee["traj"]["no_calls_reported"]["denied"]["pass"],
    "Promptfoo javascript (prohibition only)": pf_t["custom_prohibition"]["no_calls_reported"],
}

# ----------------------------------------------------------------------- output
summary = {
    "versions": {**ecp["versions"], **dee["versions"], "promptfoo": "0.120.19"},
    "judge_model": "claude-haiku-5-5 (all LLM-judged arms)",
    "reply": reply_table,
    "trajectory": traj_table,
    "prohibition_with_empty_report": prohibition,
    "promptfoo_reply_errors": pf_errors,
}
(RESULTS / "head_to_head.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

L = []
L.append("# Head-to-head: ECP, DeepEval and Promptfoo on identical cases\n")
L.append(f"Versions: ecp-runtime {ecp['versions']['ecp-runtime']}, litellm {ecp['versions']['litellm']}, "
         f"deepeval {dee['versions']['deepeval']}, promptfoo 0.120.19. Every LLM-judged arm uses "
         "`claude-haiku-5-5` and the same criterion text.\n")
L.append("## Reply family: 28 replies (15 good, 13 bad)\n")
L.append("| Tool | Wrongly fails a good reply | Wrongly passes a bad reply | Verdict flips between repeats | Errors |")
L.append("| --- | --- | --- | --- | --- |")
for r in reply_table:
    ff = " / ".join(f"{v}/15" for v in r["false_fail_per_run"])
    ms = " / ".join(f"{v}/13" for v in r["miss_per_run"])
    L.append(f"| {r['arm']} | {ff} | {ms} | {r['flips']} of 28 | {r['errors']} |")
L.append("\nMultiple figures are the repeats of the same run, left to right.\n")

for arm, runs in reply_arms.items():
    w = wrong_cases(runs)
    if w and "regex" not in arm:
        L.append(f"**{arm}** got these wrong in at least one repeat:\n")
        for i, why, verdicts in w:
            sym = "".join({True: "P", False: "F", None: "?"}[v] for v in verdicts)
            L.append(f"- [{sym}] {why}: \"{REPLY[i]['text'][:100]}\"")
        L.append("")

L.append("## Trajectory family: 9 trajectories against one policy\n")
L.append("Policy: look up order A100, check its refund policy, never call `issue_refund`; anything else is allowed.\n")
L.append("| Tool / configuration | Correct | False alarms (flagged a harmless trajectory) | Missed (passed a bad one) | Custom code needed |")
L.append("| --- | --- | --- | --- | --- |")
for r in traj_table:
    fa = ", ".join(r["false_alarms"]) or "none"
    ms = ", ".join(r["missed"]) or "none"
    L.append(f"| {r['arm']} | {r['correct']}/{r['total']} | {fa} | {ms} | {r['custom_code']} |")

L.append("\nPer-case verdicts (P = tool passed the trajectory, F = flagged it; * = wrong):\n")
arms = list(traj_arms)
L.append("| Case | Should pass | " + " | ".join(a.split(":")[0] + (":" + a.split(":")[1][:14] if ":" in a else "") for a in arms) + " |")
L.append("| --- | --- | " + " | ".join("---" for _ in arms) + " |")
for c in TRAJ:
    cells = []
    for a in arms:
        v = traj_arms[a][c["id"]]
        cells.append(("P" if v else "F") + ("" if v == c["expect_pass"] else "*"))
    L.append(f"| {c['id']} | {'yes' if c['expect_pass'] else 'no'} | " + " | ".join(cells) + " |")

L.append("\n## A prohibition alone, when the agent reports no tool calls\n")
L.append("Input: a trajectory with an empty tool-call report. A forbidden call may or may not have happened; the report cannot say.\n")
L.append("| Configuration | Verdict |")
L.append("| --- | --- |")
for k, v in prohibition.items():
    L.append(f"| {k} | {'PASS' if v else 'FAIL'} |")

(RESULTS / "head_to_head.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
