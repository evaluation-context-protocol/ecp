"""
Build a blind labelling sheet from the 28 replies.

sheet.md / sheet.csv   what an independent labeller sees: shuffled replies, the customer's
                       message, the criterion, and an empty verdict column. No source,
                       no author label, no tool result.
key.json               the author's labels, keyed by the sheet's neutral ids. Do NOT give
                       this file to the labeller.

Labellers answer one question per reply: does it satisfy the criterion? (PASS / FAIL)
"""

import csv
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE.parent / "results" / "cases.json").read_text(encoding="utf-8"))

cases = list(data["reply_cases"])
random.Random(20261027).shuffle(cases)  # fixed seed: the sheet is reproducible

rows, key = [], {}
for n, c in enumerate(cases, 1):
    rid = f"R{n:02d}"
    rows.append({
        "id": rid,
        "customer_message": data["prompts"][c["scenario"]],
        "criterion": data["criteria"][c["scenario"]],
        "reply": c["text"],
        "verdict (PASS/FAIL)": "",
    })
    key[rid] = {"author_label": c["label"], "case_id": c["id"]}

with open(HERE / "sheet.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

md = [
    "# Blind labelling sheet",
    "",
    "For each reply, decide whether it **satisfies the criterion** shown with it, "
    "using only the text on this page. Write PASS or FAIL. Please do not discuss your "
    "answers with the author or look up any tool's verdict before finishing.",
    "",
]
for r in rows:
    md += [f"## {r['id']}", "", f"**Customer:** {r['customer_message']}", "", f"**Criterion:** {r['criterion']}", "",
           f"> {r['reply']}", "", "**Verdict (PASS / FAIL):** ____", ""]
(HERE / "sheet.md").write_text("\n".join(md), encoding="utf-8")
(HERE / "key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
print(f"{len(rows)} replies -> sheet.md, sheet.csv (give these); key.json (keep private)")
