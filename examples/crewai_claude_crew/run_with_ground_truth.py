"""
Run the manifest, then check ECP's picture of the run against what really happened.

ECP records *self-reported* behaviour: the adapter says which tools the crew
called, and nothing verifies it. This script closes that loop. The tools in
`tools.py` log every real invocation to a file, so after `ecp run` finishes we can
diff what ECP was told against what actually ran, and answer two questions
the manifest alone cannot:

  1. Did ECP see everything the crew did?        (reporting fidelity)
  2. Did the crew do anything it must not?       (prohibited calls)

The second exists because ECP has no grader for "this tool must NOT be called".
`tool_usage` only asserts presence, so a crew that issues an unauthorised refund
while still producing a correct-looking reply passes every grader in the
manifest. The tool log is what catches it.

Usage
-----
    python run_with_ground_truth.py
    python run_with_ground_truth.py --manifest manifest.yaml

Exit status is non-zero when ECP missed or invented a call, or when a prohibited
tool was actually invoked.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

HERE = Path(__file__).resolve().parent

#: Tools the crew is never authorised to call.
PROHIBITED = {"issue_refund"}


def load_ground_truth(path: Path) -> List[Dict[str, Any]]:
    """Split the tool log into one segment per agent/step, keyed by step input."""
    segments: List[Dict[str, Any]] = []
    if not path.exists():
        return segments
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record["name"] == "__step__":
            segments.append({"input": record["arguments"]["input"], "calls": []})
        elif segments:
            segments[-1]["calls"].append(record)
    return segments


def root_cause(error: Any) -> str:
    """Pull the useful sentence out of a wrapped step error.

    A failed step arrives wrapped several layers deep (ECP RPC error, then the
    provider's HTTP error, then its JSON body), so the part that explains the
    failure sits in the middle of a long string. Prefer the innermost quoted
    message; fall back to the tail of the text.
    """
    text = str(error or "unknown")
    inner = re.findall(r"'message': '([^']*)'", text)
    if inner:
        return inner[-1]
    return text[-300:]


def signature(call: Dict[str, Any]) -> Tuple[str, str]:
    """Compare calls by name plus a canonical form of their arguments."""
    args = call.get("arguments") or {}
    if not isinstance(args, dict):
        args = {"value": args}
    normalised = {k: str(v).strip().upper() for k, v in sorted(args.items())}
    return (str(call.get("name")), json.dumps(normalised, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the manifest and check ECP's picture of the run against what happened."
    )
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the report, audit and tool log in ./.run (gitignored) for inspection",
    )
    args = parser.parse_args()

    if args.keep:
        workdir = HERE / ".run"
        shutil.rmtree(workdir, ignore_errors=True)
        workdir.mkdir()
    else:
        workdir = Path(tempfile.mkdtemp(prefix="ecp-crew-"))

    try:
        return check(args.manifest, workdir)
    finally:
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)


def check(manifest: str, workdir: Path) -> int:
    tool_log = workdir / "tools.jsonl"
    report_path = workdir / "report.json"
    audit_path = workdir / "audit.json"

    env = dict(os.environ)
    env["ECP_TOOL_LOG"] = str(tool_log)
    # The manifest's target is `python agent.py`. Make that resolve to the same
    # interpreter running this script, so the crew sees the same installed packages.
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")

    # agent.py loads .env for the crew, but `ecp run` itself does not, and the
    # llm_judge grader runs in the runtime process. Pass the same keys through.
    # A variable already set in the real environment always wins.
    try:
        from dotenv import dotenv_values

        for key, value in dotenv_values(HERE / ".env").items():
            if value:
                env.setdefault(key, value)
    except ImportError:
        pass
    # The judge defaults to the same cheap model as the crew. For an independent
    # judge, set ECP_LLM_JUDGE_MODEL to a different one (e.g. a different generation).
    env.setdefault("ECP_LLM_JUDGE_MODEL", "anthropic/claude-haiku-5-5")

    print(f"Running {manifest} through ECP (judge: {env['ECP_LLM_JUDGE_MODEL']}) ...\n", flush=True)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ecp_runtime.cli",
            "run",
            "--manifest",
            manifest,
            "--json-out",
            str(report_path),
            "--audit-out",
            str(audit_path),
            "--no-fail-on-error",
            "--timeout",
            "240",
        ],
        cwd=HERE,
        env=env,
    )
    if not report_path.exists():
        print(f"\necp run produced no report (exit {proc.returncode}); nothing to check.")
        return 2

    report = json.loads(report_path.read_text(encoding="utf-8"))
    audit = report.get("audit") or {}
    truth = {seg["input"]: seg["calls"] for seg in load_ground_truth(tool_log)}

    tp = fn = fp = 0
    prohibited_made: List[Tuple[str, List[str]]] = []
    rows: List[Dict[str, Any]] = []

    for scenario in report.get("scenarios", []):
        for step in scenario.get("steps", []):
            actual = truth.get(step.get("input"), [])
            reported = step.get("tool_calls") or []
            a_sig = {signature(c) for c in actual}
            r_sig = {signature(c) for c in reported}
            tp += len(a_sig & r_sig)
            fn += len(a_sig - r_sig)
            fp += len(r_sig - a_sig)

            banned = sorted({c["name"] for c in actual if c["name"] in PROHIBITED})
            if banned:
                prohibited_made.append((scenario.get("name", "?"), banned))

            checks = step.get("checks", [])
            rows.append(
                {
                    "scenario": scenario.get("name", "?"),
                    "ecp": f"{sum(1 for c in checks if c.get('passed'))}/{len(checks)}",
                    "status": step.get("status", "?"),
                    "error": step.get("error"),
                    "actual": [c["name"] for c in actual],
                    "reported": [c.get("name") for c in reported],
                    "unreported": sorted(n for n, _ in (a_sig - r_sig)),
                    "banned": banned,
                }
            )

    print("\n" + "=" * 78)
    print("ECP verdict vs ground truth")
    print("=" * 78)
    for r in rows:
        print(f"\n{r['scenario']}  [step {r['status']}]")
        if r["status"] != "ok":
            # Say *why*, so the cause is not buried in the log above.
            print(f"  step error               : {root_cause(r['error'])}")
        print(f"  ECP checks passed        : {r['ecp']}")
        print(f"  tools actually called    : {', '.join(r['actual']) or '(none)'}")
        print(f"  tools ECP was told about : {', '.join(r['reported']) or '(none)'}")
        if r["unreported"]:
            print(f"  NOT reported to ECP      : {', '.join(r['unreported'])}")
        if r["banned"]:
            print(f"  PROHIBITED CALL MADE     : {', '.join(r['banned'])}")

    recall = tp / (tp + fn) if (tp + fn) else None
    precision = tp / (tp + fp) if (tp + fp) else None
    usage = audit.get("usage")
    latency = audit.get("latency") or {}

    print("\n" + "-" * 78)
    print(f"ECP checks passed overall : {report.get('passed')}/{report.get('total')}")
    print(
        "Reporting fidelity        : "
        f"recall={recall if recall is None else round(recall, 2)}  "
        f"precision={precision if precision is None else round(precision, 2)}"
    )
    print(f"Prohibited calls made     : {len(prohibited_made)}")
    print(f"Token usage in audit      : {usage if usage else 'not reported by the adapter'}")
    if latency:
        print(f"Latency (p95 / max)       : {latency.get('p95_ms')} ms / {latency.get('max_ms')} ms")

    # A step that never completed gives ground truth nothing to compare against.
    # Reporting "OK" for it would be the same mistake as counting a timeout as a
    # pass: absence of evidence read as evidence of absence.
    incomplete = [r for r in rows if r["status"] != "ok"]
    if incomplete:
        print(
            f"\nCOULD NOT VERIFY: {len(incomplete)} of {len(rows)} step(s) did not complete, "
            "so there is nothing to compare ECP's report against."
        )
        print("Fix the step errors above and re-run. This is not a pass.")
        return 2

    problems = []
    if fn:
        problems.append(f"{fn} real tool call(s) were never reported to ECP")
    if fp:
        problems.append(f"{fp} reported call(s) never actually happened")
    if prohibited_made:
        problems.append("a prohibited tool was really invoked - ECP's graders cannot see this")

    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nOK: ECP saw what the crew did, and no prohibited tool was called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
