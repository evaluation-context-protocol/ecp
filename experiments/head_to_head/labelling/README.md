# Blind labelling

The 28-reply corpus was labelled by the study's author. This folder lets someone else
label it without seeing those labels.

1. Give the labeller **`sheet.md`** (to read) or **`sheet.csv`** (to fill in). Nothing else:
   not `key.json`, `../results/`, or `../cases.py`, which contain the author's labels.
2. They fill in PASS or FAIL for every reply, working alone, before looking at any tool's output.
3. `python score_labels.py filled_sheet.csv` reports agreement and Cohen's kappa between
   labeller and author, and lists each disagreement.

`key.json` is git-ignored so a clone of the repository does not hand it over, but the
author's labels are still in `cases.py`; blindness depends on what the labeller is given.
Regenerate the sheet with `python make_sheet.py` (fixed shuffle seed).
