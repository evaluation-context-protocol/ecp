"""
Summarise the natural-defects run.

For every trial where a refund was really issued (ground truth: the tool log), classify
who noticed:

    reply only   the reply judge failed it, `not_called` did not
    ECP only     `not_called` failed it, the reply judge passed the reply: the defect
                 was invisible to outcome grading
    both         each flagged it
    neither      nobody did

and, for the trials with no refund, how often each grader raised a false alarm.
Rows whose tool log disagrees with the adapter's report are set aside and counted,
since their ground truth is in doubt.
"""

import json
import math
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = HERE / "results" / "natural_defects_rows.jsonl"
VARIANT_ORDER = ["guarded", "no_writer_rule", "no_tool_warning", "no_review_rule", "eager"]


def wilson(k, n, z=1.96):
    """95% Wilson score interval for a proportion. Honest about small n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def pct(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({100 * k / n:.0f}%, 95% CI {100 * lo:.0f}-{100 * hi:.0f}%)" if n else "0/0"


rows = [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines()]
errored = [r for r in rows if "error" in r]
valid = [r for r in rows if "error" not in r and not r["log_mismatch"] and not r["log_corrupt_lines"]]
doubtful = [r for r in rows if "error" not in r and (r["log_mismatch"] or r["log_corrupt_lines"])]
judge_errors = [r for r in valid if r["judge_error"]]
valid = [r for r in valid if not r["judge_error"]]

by_variant = defaultdict(list)
for r in valid:
    by_variant[r["variant"]].append(r)

out = []
out.append("# Natural defects: what do LLM-made failures look like to each grader?\n")
out.append(
    f"{len(rows)} live crew runs on `claude-haiku-5-5` (5 variants x 3 scenarios x "
    f"{len(rows) // 15} each). Usable: {len(valid)}. Set aside: {len(errored)} crashed, "
    f"{len(doubtful)} with a tool log that disagreed with the adapter, "
    f"{len(judge_errors)} with a judge error.\n"
)

out.append("## How often did the crew really issue a refund?\n")
out.append("Ground truth is the tool log written by the tools themselves.\n")
out.append("| Variant | Refund really issued |")
out.append("| --- | --- |")
for v in VARIANT_ORDER:
    rs = by_variant.get(v, [])
    out.append(f"| `{v}` | {pct(sum(r['refund_issued'] for r in rs), len(rs))} |")

defects = [r for r in valid if r["refund_issued"]]
clean = [r for r in valid if not r["refund_issued"]]


def classify(r):
    reply_flag = not r["reply_ok"]
    ecp_flag = not r["ecp_ok"]
    if reply_flag and ecp_flag:
        return "both"
    if ecp_flag:
        return "ECP only"
    if reply_flag:
        return "reply only"
    return "neither"


out.append("\n## When a refund was really issued, who noticed?\n")
if defects:
    counts = defaultdict(int)
    for r in defects:
        counts[classify(r)] += 1
    out.append(f"{len(defects)} trials had a refund really issued.\n")
    out.append("| Caught by | Trials |")
    out.append("| --- | --- |")
    for k in ("both", "ECP only", "reply only", "neither"):
        out.append(f"| {k} | {counts[k]} |")
    hidden = [r for r in defects if r["reply_ok"]]
    out.append(
        f"\nOf those {len(defects)}, the reply judge passed the reply in **{len(hidden)}**: "
        f"the refund went out and the reply alone gave no sign. `not_called` flagged "
        f"**{sum(1 for r in hidden if not r['ecp_ok'])} of those {len(hidden)}**.\n"
    )
    if hidden:
        out.append("The replies that looked fine while a refund had really been issued:\n")
        for r in hidden:
            out.append(f"- `{r['variant']}` / `{r['scenario']}`: \"{r['reply'][:230]}\"")
else:
    out.append("No refund was really issued in any usable trial, so there is nothing to compare.")

out.append("\n## False alarms on trials where no refund was issued\n")
out.append(f"{len(clean)} trials.\n")
out.append("| Grader | False alarms |")
out.append("| --- | --- |")
out.append(f"| Reply judge (outcome only) | {pct(sum(1 for r in clean if not r['reply_ok']), len(clean))} |")
out.append(f"| `not_called` (tool calls) | {pct(sum(1 for r in clean if not r['ecp_ok']), len(clean))} |")

out.append("\n## Where the refunds happened\n")
out.append("| Variant | Scenario | Refund issued |")
out.append("| --- | --- | --- |")
for v in VARIANT_ORDER:
    for s in ("pressure", "eligible", "ineligible_push"):
        rs = [r for r in by_variant.get(v, []) if r["scenario"] == s]
        if rs:
            out.append(f"| `{v}` | {s} | {sum(r['refund_issued'] for r in rs)}/{len(rs)} |")

report = "\n".join(out) + "\n"
(HERE / "results" / "natural_defects.md").write_text(report, encoding="utf-8")
print(report)
