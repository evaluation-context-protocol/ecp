"""Compare ECP, DeepEval and Promptfoo on the 90 saved crew runs -> crosscheck.md."""

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
cases = {c["id"]: c for c in data["cases"]}
dee = {r["id"]: r for r in json.loads((HERE / "deepeval.json").read_text(encoding="utf-8"))}
pf = {}
for r in json.loads((HERE / "promptfoo.json").read_text(encoding="utf-8"))["results"]["results"]:
    m = r["metadata"]
    pf[(m["id"], m["kind"])] = None if r.get("failureReason") == 2 else bool(r["success"])


def wilson(k, n, z=1.96):
    if not n:
        return "n/a"
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return f"{100 * max(0, c - h):.0f}-{100 * min(1, c + h):.0f}%"


# passes[tool][kind][id] -> True (grader passed the run) / False / None (errored)
passes = {
    "ECP": {"reply": {i: c["ecp_reply_ok"] for i, c in cases.items()}, "tools": {i: c["ecp_ok"] for i, c in cases.items()}},
    "DeepEval": {"reply": {i: dee[i]["reply_pass"] for i in cases}, "tools": {i: dee[i]["tools_pass"] for i in cases}},
    "Promptfoo": {"reply": {i: pf[(i, "reply")] for i in cases}, "tools": {i: pf[(i, "tools")] for i in cases}},
}
bad = [i for i, c in cases.items() if c["refund_issued"]]
good = [i for i, c in cases.items() if not c["refund_issued"]]

out = [
    "# Saved natural-defect runs scored by three tools",
    "",
    f"{len(cases)} saved crew runs ({len(bad)} where the tools' own log shows a refund was really issued, "
    f"{len(good)} where none was). Each tool is given the same two things ECP's contract carries: the reply "
    "and the tool-call names the adapter reported. Judge arms use `claude-haiku-5-5` with the same criterion text.",
    "",
    "| Tool | Check | Caught real refunds | False alarms on clean runs | Errored |",
    "|---|---|---|---|---|",
]
names = {"reply": "reply judge (outcome only)", "tools": "tool-call prohibition"}
for tool, views in passes.items():
    for kind, v in views.items():
        caught = sum(v[i] is False for i in bad)
        false = sum(v[i] is False for i in good)
        err = sum(v[i] is None for i in cases)
        out.append(f"| {tool} | {names[kind]} | {caught}/{len(bad)} | {false}/{len(good)} (95% CI {wilson(false, len(good))}) | {err} |")

out += ["", "## Verdict agreement between tools (runs where neither errored)", "",
        "| Check | ECP vs DeepEval | ECP vs Promptfoo | DeepEval vs Promptfoo |", "|---|---|---|---|"]
for kind in ("reply", "tools"):
    cells = []
    for a, b in (("ECP", "DeepEval"), ("ECP", "Promptfoo"), ("DeepEval", "Promptfoo")):
        ids = [i for i in cases if passes[a][kind][i] is not None and passes[b][kind][i] is not None]
        agree = sum(passes[a][kind][i] == passes[b][kind][i] for i in ids)
        cells.append(f"{agree}/{len(ids)}")
    out.append(f"| {names[kind]} | " + " | ".join(cells) + " |")

out += ["", "## Where the reply judges disagreed with each other or missed a real refund", ""]
for i in cases:
    votes = {t: passes[t]["reply"][i] for t in passes}
    if len(set(votes.values())) > 1 or (cases[i]["refund_issued"] and votes["ECP"] is False):
        out.append(f"- `{i}` real refund={cases[i]['refund_issued']}: " + ", ".join(f"{t}={'pass' if v else 'FAIL' if v is False else 'error'}" for t, v in votes.items()))

(HERE / "crosscheck.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
