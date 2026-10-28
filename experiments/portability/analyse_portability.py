"""Summarise results/portability_rows.jsonl (or --rows FILE) into results/<name>.md."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRAMEWORKS = ("crewai", "langchain", "pydanticai", "llamaindex")


def kind(check):
    if check["type"] == "execution":
        return "execution"
    if check["type"] == "llm_judge":
        return "judge"
    why = check.get("reasoning", "")
    return "not_called" if ("not called" in why or "Forbidden" in why or "Cannot verify" in why) else "tool present"


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", default=str(HERE / "results" / "portability_rows.jsonl"))
    ap.add_argument("--out", default=str(HERE / "results" / "portability.md"))
    args = ap.parse_args()
    rows = [json.loads(line) for line in Path(args.rows).read_text(encoding="utf-8").splitlines() if line.strip()]
    # Two runners may have written the same (framework, rep) key; each is an independent
    # live run, so number the repeats as further repetitions instead of dropping them.
    seen = Counter()
    for r in rows:
        key = (r["framework"], r["rep"], r["scenario"])
        r["rep"] = r["rep"] + 100 * seen[key]
        seen[key] += 1
    fws = [f for f in FRAMEWORKS if any(r["framework"] == f for r in rows)]
    out = []

    # 1. Step completion and check pass rates.
    out += ["## Step completion and check pass rates", "",
            "| framework | steps completed | tool present | not_called | llm_judge |", "|---|---|---|---|---|"]
    for fw in fws:
        mine = [r for r in rows if r["framework"] == fw]
        ok = sum(r["status"] == "ok" for r in mine)
        tally = defaultdict(lambda: [0, 0])
        for r in mine:
            for c in r["checks"]:
                k = kind(c)
                if k != "execution":
                    tally[k][1] += 1
                    tally[k][0] += bool(c["passed"])
        out.append(f"| {fw} | {pct(ok, len(mine))} | " + " | ".join(pct(*tally[k]) for k in ("tool present", "not_called", "judge")) + " |")

    # 2. Reporting fidelity: adapter-reported vs real tool calls (names, per completed step).
    out += ["", "## Reporting fidelity (adapter vs tools' own log, completed steps)", "",
            "| framework | steps | recall | precision | exact name-multiset match |", "|---|---|---|---|---|"]
    for fw in fws:
        steps = [r for r in rows if r["framework"] == fw and r["status"] == "ok"]
        tp = fn = fp = exact = 0
        for r in steps:
            a, b = Counter(r["actual_tools"]), Counter(r["reported_tools"])
            common = sum((a & b).values())
            tp += common
            fn += sum(a.values()) - common
            fp += sum(b.values()) - common
            exact += a == b
        rec = f"{tp}/{tp + fn}" if tp + fn else "n/a"
        prec = f"{tp}/{tp + fp}" if tp + fp else "n/a"
        out.append(f"| {fw} | {len(steps)} | {rec} | {prec} | {pct(exact, len(steps))} |")

    # 2b. Is the not_called verdict right? Compare it to whether issue_refund really ran.
    out += ["", "## `not_called issue_refund` verdict vs what really happened", "",
            "| framework | refund really issued | not_called flagged it | verdict correct |", "|---|---|---|---|"]
    for fw in fws:
        steps = [r for r in rows if r["framework"] == fw and r["status"] == "ok"]
        issued = flagged = right = 0
        for r in steps:
            real = "issue_refund" in r["actual_tools"]
            chk = [c for c in r["checks"] if kind(c) == "not_called"]
            if not chk:
                continue
            fail = not chk[0]["passed"]
            issued += real
            flagged += real and fail
            right += fail == real
        out.append(f"| {fw} | {issued}/{len(steps)} steps | {flagged}/{issued} | {pct(right, len(steps))} |")

    # 3. Cross-framework agreement on the same (rep, scenario, check).
    cells = defaultdict(dict)
    for r in rows:
        if r["status"] != "ok":
            continue
        for i, c in enumerate(r["checks"]):
            cells[(r["rep"], r["scenario"], i)][r["framework"]] = (kind(c), bool(c["passed"]))
    out += ["", "## Cross-framework verdict agreement", "",
            "A cell is one check in one repetition; it counts only when every framework completed that step.", "",
            "| check kind | cells | all frameworks agree | disagreements |", "|---|---|---|---|"]
    by_kind = defaultdict(lambda: [0, 0])
    for key, per in cells.items():
        if len(per) == len(fws):
            k = next(iter(per.values()))[0]
            by_kind[k][1] += 1
            by_kind[k][0] += len({v[1] for v in per.values()}) == 1
    for k, (agree, n) in sorted(by_kind.items()):
        out.append(f"| {k} | {n} | {pct(agree, n)} | {n - agree} |")

    # 4. What differs between frameworks beyond the verdict.
    out += ["", "## Tool-call sequences per scenario (most common, with count)", "",
            "| scenario | " + " | ".join(fws) + " |", "|---|" + "---|" * len(fws)]
    for sc in sorted({r["scenario"] for r in rows if r["scenario"]}):
        cols = []
        for fw in fws:
            seqs = Counter(" → ".join(r["actual_tools"]) or "(none)" for r in rows if r["framework"] == fw and r["scenario"] == sc)
            seq, n = seqs.most_common(1)[0] if seqs else ("-", 0)
            cols.append(f"{seq} ×{n}/{sum(seqs.values())}")
        out.append(f"| {sc} | " + " | ".join(cols) + " |")

    out += ["", "## Optional fields reported", "", "| framework | usage | evaluation_context |", "|---|---|---|"]
    for fw in fws:
        mine = [r for r in rows if r["framework"] == fw and r["status"] == "ok"]
        out.append(f"| {fw} | {pct(sum(bool(r['usage']) for r in mine), len(mine))} | {pct(sum(r['eval_context_chars'] > 0 for r in mine), len(mine))} |")

    errs = Counter((r["framework"], str(r["error"])[-110:]) for r in rows if r["status"] != "ok")
    if errs:
        out += ["", "## Step errors", ""]
        out += [f"- {fw}: {msg} ×{n}" for (fw, msg), n in errs.items()]

    reps = len({r["rep"] for r in rows})
    out = [f"# Portability results ({reps} repetition(s), {len(rows)} steps)", ""] + out
    Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out).encode("ascii", "replace").decode())


if __name__ == "__main__":
    main()
