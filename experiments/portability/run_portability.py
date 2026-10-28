"""
Run one manifest against the same refund desk built in several agent frameworks.

For every (framework, repetition) it runs `ecp run` on that framework's generated
manifest (identical to the others except for `target:`), and records for each step:
the checks ECP made, the tool calls the adapter *reported*, and the tool calls the
tools *actually made* (the ground-truth log written by the tools themselves).

Rows are appended to results/portability_rows.jsonl as they finish, so an
interrupted run resumes. Repetitions are interleaved across frameworks so that
drift in the API or the model affects all of them alike.

Usage:  run_portability.py [--reps 5] [--frameworks crewai langchain ...]
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RESULTS = HERE / "results"
MODE = os.environ.get("ECP_PORTABILITY_MODE", "guarded")
ROWS = RESULTS / ("portability_rows.jsonl" if MODE == "guarded" else f"portability_rows_{MODE}.jsonl")

sys.path.insert(0, str(HERE))
import make_manifests  # noqa: E402


def done_keys():
    if not ROWS.exists():
        return set()
    return {(r["framework"], r["rep"]) for r in map(json.loads, ROWS.read_text(encoding="utf-8").splitlines() if ROWS.exists() else [])}


def ground_truth(path: Path):
    segments = []
    if not path.exists():
        return segments
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["name"] == "__step__":
            segments.append({"input": rec["arguments"]["input"], "calls": []})
        elif segments:
            segments[-1]["calls"].append(rec)
    return segments


def run_one(framework: str, rep: int):
    work = Path(tempfile.mkdtemp(prefix=f"ecp-port-{framework}-"))
    log, report_path = work / "tools.jsonl", work / "report.json"
    env = dict(os.environ)
    for k, v in dotenv_values(REPO / "examples" / "crewai_claude_crew" / ".env").items():
        if v:
            env.setdefault(k, v)
    env.setdefault("ECP_LLM_JUDGE_MODEL", "anthropic/claude-haiku-5-5")
    env["ECP_TOOL_LOG"] = str(log)
    manifest = HERE / "manifests" / f"manifest_{framework}.yaml"
    proc = subprocess.run(
        [sys.executable, "-m", "ecp_runtime.cli", "run", "--manifest", str(manifest),
         "--json-out", str(report_path), "--no-fail-on-error", "--timeout", "240"],
        cwd=REPO, env=env, capture_output=True, text=True,
    )
    if not report_path.exists():
        return [{"framework": framework, "rep": rep, "scenario": None, "run_error": (proc.stderr or proc.stdout)[-400:]}]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    truth = {s["input"]: s["calls"] for s in ground_truth(log)}
    rows = []
    for sc in report.get("scenarios", []):
        for st in sc.get("steps", []):
            actual = truth.get(st.get("input"), [])
            rows.append({
                "framework": framework, "rep": rep, "scenario": sc.get("name"),
                "status": st.get("status"), "error": st.get("error"),
                "reply": st.get("public_output") or st.get("output"),
                "checks": st.get("checks", []),
                "actual_tools": [c["name"] for c in actual],
                "reported_tools": [c.get("name") for c in st.get("tool_calls") or []],
                "usage": st.get("usage"),
                "eval_context_chars": len(str(st.get("evaluation_context") or "")),
                "step_keys": sorted(st.keys()),
            })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--frameworks", nargs="*", default=list(make_manifests.FRAMEWORKS))
    args = ap.parse_args()
    make_manifests.build(tuple(args.frameworks))
    RESULTS.mkdir(exist_ok=True)
    done = done_keys()
    for rep in range(args.reps):
        todo = [fw for fw in args.frameworks if (fw, rep) not in done]
        if not todo:
            continue
        with ThreadPoolExecutor(len(todo)) as pool:
            for rows in pool.map(lambda fw: run_one(fw, rep), todo):
                with open(ROWS, "a", encoding="utf-8") as fh:
                    for r in rows:
                        fh.write(json.dumps(r) + "\n")
                fw = rows[0]["framework"]
                ok = sum(1 for r in rows for c in r.get("checks", []) if c.get("passed"))
                n = sum(len(r.get("checks", [])) for r in rows)
                print(f"rep {rep} {fw:11} checks {ok}/{n}", flush=True)


if __name__ == "__main__":
    main()
