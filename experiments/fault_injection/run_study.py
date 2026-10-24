"""
Study 1: what does trajectory grading catch that outcome grading misses?

Method
------
For each entry in the taxonomy, generate a real ECP agent whose final answer is
**correct** and whose trajectory carries that defect. Run it through the real
`ecp` CLI once per grading configuration and compare verdicts.

A defect counts as detected when outcome-only grading passes it and a trajectory
configuration fails it. Defects that outcome grading already catches are
excluded, since they need no trajectory evidence to find. The headline quantity
is therefore detection rate *conditional on a correct final answer*.

Two trajectory configurations are reported separately:

- ``structured``: assertions over machine-readable ``tool_calls``.
- ``contract``: adds a text assertion over free-form ``evaluation_context``.

They are not aggregated, because the taxonomy includes a non-defect probe
(correct answer, correct trajectory, different wording) whose only purpose is to
measure what the text assertion costs. A detection rate without its
false-positive rate is not interpretable.

Every entry also carries a prediction of which configurations should flag it.
The study asserts prediction against measurement and exits non-zero on
disagreement, so reported numbers cannot drift from the taxonomy's claims.

Usage
-----
    python experiments/fault_injection/run_study.py
    python experiments/fault_injection/run_study.py --repeat 3 --keep
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
RESULTS_DIR = HERE / "results"

sys.path.insert(0, str(HERE))
from taxonomy import (  # noqa: E402
    CORRECT_ANSWER,
    DEFECTS,
    GRADER_SETS,
    Defect,
    GraderSet,
)

AGENT_TEMPLATE = '''"""Generated for the fault-injection study. Case: {defect_key}."""
import sys

sys.path.insert(0, {sdk_src!r})

from ecp import Result, agent, on_step, serve


@agent(
    name="FaultInjected_{defect_key}",
    capabilities={{"tool_calls": {{}}, "evaluation_context": {{}}}},
)
class FaultInjectedAgent:
    @on_step
    def step(self, user_input: str) -> Result:
        # The final answer is always correct. Only the trajectory varies.
        return Result(
            public_output={answer!r},
            evaluation_context={context!r},
            tool_calls={tool_calls!r},
        )


if __name__ == "__main__":
    serve(FaultInjectedAgent())
'''


@dataclass
class Outcome:
    """One (case, grading configuration) run."""

    defect: str
    grader_set: str
    passed: int
    total: int
    failed_graders: List[str]
    duration_ms: float
    exit_reason: str

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.passed == self.total


def _write_agent(workdir: Path, defect: Defect) -> Path:
    path = workdir / f"agent_{defect.key}.py"
    path.write_text(
        AGENT_TEMPLATE.format(
            defect_key=defect.key,
            sdk_src=str(REPO_ROOT / "sdk" / "python" / "src"),
            answer=CORRECT_ANSWER,
            context=defect.evaluation_context,
            tool_calls=defect.tool_calls,
        ),
        encoding="utf-8",
    )
    return path


def _write_manifest(
    workdir: Path, defect: Defect, grader_set: GraderSet, agent_path: Path
) -> Path:
    manifest = {
        "manifest_version": "v1",
        "name": f"{defect.key} / {grader_set.key}",
        "target": f"python {agent_path.name}",
        "scenarios": [
            {
                "name": "refund eligibility",
                "steps": [
                    {
                        "input": "Is order A100 eligible for a refund, and for how much?",
                        "graders": grader_set.graders,
                    }
                ],
            }
        ],
    }
    path = workdir / f"manifest_{defect.key}_{grader_set.key}.yaml"
    # JSON is a valid YAML subset, so this avoids a yaml dependency here and
    # keeps the generated manifest unambiguous.
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _run(workdir: Path, manifest: Path) -> Dict[str, Any]:
    report = workdir / f"{manifest.stem}.report.json"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO_ROOT / "runtime" / "python" / "src"),
            str(REPO_ROOT / "sdk" / "python" / "src"),
            env.get("PYTHONPATH", ""),
        ]
    ).strip(os.pathsep)

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ecp_runtime.cli",
            "run",
            "--manifest",
            manifest.name,
            "--json-out",
            report.name,
            "--no-fail-on-error",
            "--timeout",
            "30",
        ],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
    )
    if not report.exists():
        raise RuntimeError(
            f"no report produced for {manifest.name}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return json.loads(report.read_text(encoding="utf-8"))


def _collect(defect: Defect, grader_set: GraderSet, payload: Dict[str, Any]) -> Outcome:
    failed: List[str] = []
    for scenario in payload.get("scenarios", []):
        for step in scenario.get("steps", []):
            for check in step.get("checks", []):
                if not check.get("passed"):
                    failed.append(f"{check.get('type')}:{check.get('field', '?')}")
    audit = payload.get("audit") or {}
    return Outcome(
        defect=defect.key,
        grader_set=grader_set.key,
        passed=int(payload.get("passed", 0)),
        total=int(payload.get("total", 0)),
        failed_graders=failed,
        duration_ms=float(audit.get("duration_ms", 0.0)),
        exit_reason=str(payload.get("exit_reason", "unknown")),
    )


def run_once(workdir: Path) -> List[Outcome]:
    outcomes: List[Outcome] = []
    for defect in DEFECTS:
        agent_path = _write_agent(workdir, defect)
        for grader_set in GRADER_SETS:
            manifest = _write_manifest(workdir, defect, grader_set, agent_path)
            outcomes.append(_collect(defect, grader_set, _run(workdir, manifest)))
    return outcomes


def analyse(outcomes: List[Outcome]) -> Dict[str, Any]:
    by_key: Dict[str, Dict[str, Outcome]] = {}
    for o in outcomes:
        by_key.setdefault(o.defect, {})[o.grader_set] = o

    config_keys = [g.key for g in GRADER_SETS]
    trajectory_keys = [k for k in config_keys if k != "outcome_only"]

    control = by_key.get("clean", {})
    control_ok = bool(control) and all(o.all_passed for o in control.values())

    rows: List[Dict[str, Any]] = []
    mismatches: List[str] = []

    for defect in DEFECTS:
        if defect.key == "clean":
            continue
        runs = by_key.get(defect.key, {})
        if not all(k in runs for k in config_keys):
            continue

        # Flagged = this configuration failed at least one grader.
        flagged = {k: not runs[k].all_passed for k in config_keys}
        measured = frozenset(k for k, v in flagged.items() if v)

        if measured != defect.flagged_by:
            mismatches.append(
                f"{defect.key}: taxonomy predicts flagged_by={sorted(defect.flagged_by)}, "
                f"measured={sorted(measured)}"
            )

        rows.append(
            {
                "defect": defect.key,
                "label": defect.label,
                "channel": defect.channel,
                "is_defect": defect.is_defect,
                "slips_past_outcome_grading": not flagged["outcome_only"],
                "flagged": flagged,
                "failed_graders": {k: runs[k].failed_graders for k in config_keys},
                "notes": defect.notes,
            }
        )

    eligible = [r for r in rows if r["is_defect"] and r["slips_past_outcome_grading"]]
    probes = [r for r in rows if not r["is_defect"]]

    per_config: Dict[str, Any] = {}
    for key in trajectory_keys:
        detected = [r for r in eligible if r["flagged"][key]]
        false_positives = [r for r in probes if r["flagged"][key]]
        per_config[key] = {
            "eligible_defects": len(eligible),
            "detected": len(detected),
            "detection_rate": round(len(detected) / len(eligible), 4) if eligible else None,
            "probes": len(probes),
            "false_positives": len(false_positives),
            "false_positive_rate": (
                round(len(false_positives) / len(probes), 4) if probes else None
            ),
            "detected_keys": [r["defect"] for r in detected],
            "false_positive_keys": [r["defect"] for r in false_positives],
        }

    per_channel: Dict[str, Dict[str, int]] = {}
    for r in eligible:
        bucket = per_channel.setdefault(
            r["channel"], {"eligible": 0, "structured": 0, "contract": 0}
        )
        bucket["eligible"] += 1
        for key in trajectory_keys:
            if r["flagged"].get(key):
                bucket[key] = bucket.get(key, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "control_passed_all_configurations": control_ok,
        "configurations": {g.key: g.description for g in GRADER_SETS},
        "defects_eligible": len(eligible),
        "non_defect_probes": len(probes),
        "per_configuration": per_config,
        "per_channel": per_channel,
        "rows": rows,
        "taxonomy_prediction_mismatches": mismatches,
    }


def _mark(flagged: bool, is_defect: bool) -> str:
    if flagged:
        return "**caught**" if is_defect else "FALSE POSITIVE"
    return "missed" if is_defect else "pass"


def render_markdown(summary: Dict[str, Any]) -> str:
    cfg = summary["per_configuration"]

    lines = [
        "# Study 1 - Fault injection",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "Every injected defect leaves the **final answer correct**, so outcome-only",
        "grading passes it. Detection rate is therefore conditional on a correct",
        "final answer, which is the quantity of interest.",
        "",
        "Two trajectory configurations are reported separately because they differ in",
        "kind. `structured` asserts over machine-readable `tool_calls`. `contract`",
        "adds a text assertion over free-form `evaluation_context` prose. The",
        "false-positive column is why they are not aggregated.",
        "",
        "## Headline",
        "",
        "| Configuration | Defects | Detected | Detection rate | Probes | False positives | FP rate |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, label in (
        ("structured", "Structured trajectory"),
        ("contract", "Full contract"),
    ):
        c = cfg.get(key, {})
        lines.append(
            f"| {label} | {c.get('eligible_defects')} | {c.get('detected')} | "
            f"**{c.get('detection_rate')}** | {c.get('probes')} | "
            f"{c.get('false_positives')} | {c.get('false_positive_rate')} |"
        )

    lines += [
        "",
        "Control (no defect) passed every configuration: "
        f"`{summary['control_passed_all_configurations']}`",
        "",
        "## Per evidence channel (structured configuration)",
        "",
        "| Channel | Eligible defects | Detected | Rate |",
        "| --- | --- | --- | --- |",
    ]
    for channel, c in sorted(summary["per_channel"].items()):
        rate = round(c["structured"] / c["eligible"], 2) if c["eligible"] else "-"
        lines.append(f"| `{channel}` | {c['eligible']} | {c['structured']} | {rate} |")

    lines += [
        "",
        "## Per case",
        "",
        "| Case | Defect? | Channel | Outcome only | Structured | Contract |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in summary["rows"]:
        f = r["flagged"]
        lines.append(
            f"| {r['label']} | {'yes' if r['is_defect'] else 'no'} | `{r['channel']}` | "
            f"{_mark(f['outcome_only'], r['is_defect'])} | "
            f"{_mark(f['structured'], r['is_defect'])} | "
            f"{_mark(f['contract'], r['is_defect'])} |"
        )

    missed = [r for r in summary["rows"] if r["is_defect"] and not r["flagged"]["contract"]]
    if missed:
        lines += ["", "## Not expressible in ECP's current grader vocabulary", ""]
        for r in missed:
            lines.append(f"- **{r['label']}**: {r['notes']}")

    fps = [r for r in summary["rows"] if not r["is_defect"] and r["flagged"]["contract"]]
    if fps:
        lines += ["", "## False positives", ""]
        for r in fps:
            lines.append(f"- **{r['label']}**: {r['notes']}")

    if summary["taxonomy_prediction_mismatches"]:
        lines += ["", "## Prediction mismatches (FAIL)", ""]
        for m in summary["taxonomy_prediction_mismatches"]:
            lines.append(f"- {m}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fault-injection study for ECP.")
    parser.add_argument(
        "--repeat", type=int, default=1, help="repetitions (the agents are deterministic)"
    )
    parser.add_argument(
        "--keep", action="store_true", help="keep the generated agents and manifests"
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_outcomes: List[Outcome] = []
    holder: Optional[tempfile.TemporaryDirectory] = None

    try:
        for rep in range(args.repeat):
            if args.keep:
                workdir = RESULTS_DIR / f"workdir_rep{rep}"
                workdir.mkdir(parents=True, exist_ok=True)
            else:
                holder = tempfile.TemporaryDirectory()
                workdir = Path(holder.name)
            print(f"running repetition {rep + 1}/{args.repeat}")
            all_outcomes.extend(run_once(workdir))
            if holder is not None:
                holder.cleanup()
                holder = None
    finally:
        if holder is not None:
            holder.cleanup()

    summary = analyse(all_outcomes)
    summary["repetitions"] = args.repeat
    summary["raw_outcomes"] = [asdict(o) for o in all_outcomes]

    (RESULTS_DIR / "study1_fault_injection.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = render_markdown(summary)
    (RESULTS_DIR / "study1_fault_injection.md").write_text(report, encoding="utf-8")

    print()
    # Write bytes directly: the console codepage on Windows cannot encode some
    # of the report's characters.
    sys.stdout.buffer.write(report.encode("utf-8", "replace"))
    sys.stdout.flush()

    if not summary["control_passed_all_configurations"]:
        print("\nFAIL: the control agent did not pass every configuration; results invalid.")
        return 1
    if summary["taxonomy_prediction_mismatches"]:
        print("\nFAIL: taxonomy predictions disagree with measurement (see above).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
