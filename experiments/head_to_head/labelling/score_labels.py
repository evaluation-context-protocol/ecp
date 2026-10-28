"""
Compare a labeller's filled-in sheet with the author's labels and with the tools.

Usage: score_labels.py FILLED_SHEET.csv
Reports agreement and Cohen's kappa between labeller and author, and lists every reply where they differ.
The tools' own scores (head_to_head.md) use the author's labels; where the labeller
disagrees, those scores should be recomputed with the labeller's label for that reply.
"""

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
key = json.loads((HERE / "key.json").read_text(encoding="utf-8"))
lab = {r["id"]: r["verdict (PASS/FAIL)"].strip().upper() for r in csv.DictReader(open(sys.argv[1], encoding="utf-8"))}
missing = [i for i in key if lab.get(i) not in ("PASS", "FAIL")]
if missing:
    sys.exit(f"unfilled or invalid verdicts for: {', '.join(missing)}")

author = {i: ("PASS" if k["author_label"] == "good" else "FAIL") for i, k in key.items()}
n = len(key)
agree = sum(author[i] == lab[i] for i in key)
po = agree / n
pa = sum(author[i] == "PASS" for i in key) / n
pl = sum(lab[i] == "PASS" for i in key) / n
pe = pa * pl + (1 - pa) * (1 - pl)
kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
print(f"labeller vs author: {agree}/{n} agree, Cohen's kappa {kappa:.2f}")
for i in key:
    if author[i] != lab[i]:
        print(f"  disagreement {i} ({key[i]['case_id']}): author={author[i]} labeller={lab[i]}")
