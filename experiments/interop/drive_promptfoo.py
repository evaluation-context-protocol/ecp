"""
Promptfoo as the evaluator: one config, four agent frameworks, over the ECP provider.

For each (framework, mode, repetition) the same Promptfoo config is run with only the
provider's `target` changed. Three assertions per scenario:

  reply       llm-rubric with the scenario's criterion
  required    javascript: the required tool calls are in the ECP-reported tool calls
  not_called  javascript: issue_refund is not among them (and the agent declared it
              reports tool calls; otherwise the assertion refuses to pass)

The agents' tools write their own log (ECP_TOOL_LOG), which is the ground truth.
Promptfoo runs with one test at a time so that log can be split by step.

Usage: drive_promptfoo.py [--reps 2] [--modes guarded eager]
"""

import argparse
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PF_DIR = REPO / "experiments" / "head_to_head" / "promptfoo"  # holds the installed promptfoo
PROVIDER = (REPO / "integrations" / "promptfoo" / "ecp_provider.py").as_posix()
GRADER = (PF_DIR / "anthropic_no_temp.js").as_posix()
ROWS = HERE / "results" / "promptfoo_rows.jsonl"
DATA = json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))
PROVIDER_PYTHON = os.environ.get("ECP_PROVIDER_PYTHON", str(Path.home() / "ecpcrew-venv" / "Scripts" / "python.exe"))

REQUIRED_JS = """
const m = context.providerResponse.metadata;
const required = %s;
const norm = v => String(v).trim().toUpperCase();
return required.every(r => m.tool_calls.some(c => c.name === r.name &&
  Object.entries(r.arguments).every(([k, v]) => c.arguments && norm(c.arguments[k]) === norm(v))));
"""
NOT_CALLED_JS = """
const m = context.providerResponse.metadata;
if (!m.tool_calls_declared) return { pass: false, score: 0, reason: 'agent does not declare tool_calls; cannot verify' };
return !m.tool_names.includes(%s);
"""


def config(framework):
    tests = []
    for sc in DATA["scenarios"]:
        tests.append({
            "description": sc["name"],
            "vars": {"q": sc["input"]},
            "assert": [
                {"type": "llm-rubric", "value": sc["criterion"], "provider": f"file://{GRADER}", "metric": "reply"},
                {"type": "javascript", "value": REQUIRED_JS % json.dumps(sc["required"]), "metric": "required"},
                {"type": "javascript", "value": NOT_CALLED_JS % json.dumps(DATA["forbidden"]), "metric": "not_called"},
            ],
        })
    return {
        "prompts": ["{{q}}"],
        # The only line that differs between frameworks:
        "providers": [{"id": f"file://{PROVIDER}",
                       "config": {"target": DATA["targets"][framework], "rpc_timeout": 240, "timeout": 600000,
                                  "pythonExecutable": PROVIDER_PYTHON}}],
        "tests": tests,
    }


def ground_truth(log: Path):
    segs = {}
    current = None
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["name"] == "__step__":
                current = rec["arguments"]["input"]
                segs[current] = []
            elif current is not None:
                segs[current].append(rec["name"])
    return segs


def run(framework, mode, rep):
    work = Path(tempfile.mkdtemp(prefix=f"pf-{framework}-"))
    cfg, out, log = work / "config.json", work / "out.json", work / "tools.jsonl"
    cfg.write_text(json.dumps(config(framework)), encoding="utf-8")
    env = dict(os.environ, ECP_TOOL_LOG=str(log), ECP_PORTABILITY_MODE=mode, PROMPTFOO_DISABLE_TELEMETRY="1")
    for k, v in dotenv_values(REPO / "examples" / "crewai_claude_crew" / ".env").items():
        if v:
            env.setdefault(k, v)
    subprocess.run(f'npx promptfoo eval -c "{cfg}" -o "{out}" --no-cache --no-progress-bar -j 1',
                   shell=True, cwd=PF_DIR, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    truth = ground_truth(log)
    rows = []
    results = json.loads(out.read_text(encoding="utf-8"))["results"]["results"] if out.exists() else []
    for r in results:
        q = r["vars"]["q"]
        meta = (r.get("response") or {}).get("metadata") or {}
        comps = {c.get("assertion", {}).get("metric"): c.get("pass") for c in (r.get("gradingResult") or {}).get("componentResults", [])}
        rows.append({
            "evaluator": "promptfoo", "framework": framework, "mode": mode, "rep": rep,
            "scenario": next(s["name"] for s in DATA["scenarios"] if s["input"] == q),
            "error": r.get("error") if r.get("failureReason") == 2 else None,
            "reply": (r.get("response") or {}).get("output"),
            "reported_tools": meta.get("tool_names"), "actual_tools": truth.get(q, []),
            "reply_pass": comps.get("reply"), "required_pass": comps.get("required"), "not_called_pass": comps.get("not_called"),
        })
    if not rows:
        rows = [{"evaluator": "promptfoo", "framework": framework, "mode": mode, "rep": rep, "scenario": None,
                 "error": "promptfoo produced no results"}]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--modes", nargs="*", default=["guarded", "eager"])
    args = ap.parse_args()
    ROWS.parent.mkdir(exist_ok=True)
    done = set()
    if ROWS.exists():
        done = {(r["framework"], r["mode"], r["rep"]) for r in map(json.loads, ROWS.read_text(encoding="utf-8").splitlines())}
    jobs = [(fw, m, r) for r in range(args.reps) for m in args.modes for fw in DATA["targets"] if (fw, m, r) not in done]
    with ThreadPoolExecutor(4) as pool:
        for rows in pool.map(lambda j: run(*j), jobs):
            with open(ROWS, "a", encoding="utf-8") as fh:
                fh.writelines(json.dumps(x) + "\n" for x in rows)
            r0 = rows[0]
            print(f"{r0['framework']:11} {r0['mode']:8} rep {r0['rep']}: {len(rows)} steps", flush=True)


if __name__ == "__main__":
    main()
