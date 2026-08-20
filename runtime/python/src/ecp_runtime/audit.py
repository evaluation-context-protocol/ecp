"""
ecp_runtime.audit
=================
Builds the structured telemetry payload emitted after every evaluation run.

The audit record answers the questions an auditor asks after the fact: what was
run, against which agent, how long each step took, how many tokens it consumed,
and - critically - whether every step actually executed or whether the run
degraded (timeout, crash, wall-clock budget).

``build_audit`` is a pure function over the scenario records the runner already
collects, so the audit payload can never drift from what the report shows.
"""

from __future__ import annotations

import hashlib
import platform
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

AUDIT_VERSION = "1"

#: Step outcomes that mean the agent answered and the graders ran.
STATUS_OK = "ok"
#: Step outcomes that mean the agent failed to answer.
STATUS_FAILED = "failed"
#: Step outcomes that mean the step never ran.
STATUS_SKIPPED = "skipped"

USAGE_FIELDS = ("input_tokens", "output_tokens", "total_tokens")


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with a trailing Z."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def runtime_version() -> str:
    try:
        from importlib.metadata import version

        return version("ecp-runtime")
    except Exception:  # pragma: no cover - metadata missing in source checkouts
        return "unknown"


def manifest_digest(manifest_path: Optional[str]) -> Optional[str]:
    """SHA-256 of the manifest file, so a report can be tied to exact inputs."""
    if not manifest_path:
        return None
    try:
        data = Path(manifest_path).read_bytes()
    except OSError:
        return None
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def merge_usage(records: Iterable[Optional[Dict[str, Any]]]) -> Optional[Dict[str, int]]:
    """Sum per-step token usage. Returns None when no step reported usage."""
    totals: Dict[str, int] = {}
    seen = False
    for record in records:
        if not isinstance(record, dict):
            continue
        for field in USAGE_FIELDS:
            value = record.get(field)
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            totals[field] = totals.get(field, 0) + value
            seen = True
    if not seen:
        return None
    if "total_tokens" not in totals and {"input_tokens", "output_tokens"} <= totals.keys():
        totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]
    return totals


def latency_summary(durations: List[float]) -> Dict[str, float]:
    """Aggregate step latencies. Empty input yields zeros rather than nulls."""
    if not durations:
        return {"total_ms": 0.0, "mean_ms": 0.0, "max_ms": 0.0, "p95_ms": 0.0}
    ordered = sorted(durations)
    # Nearest-rank p95: index of the smallest value at or above the 95th percentile.
    rank = max(1, -(-95 * len(ordered) // 100))
    return {
        "total_ms": round(sum(ordered), 3),
        "mean_ms": round(sum(ordered) / len(ordered), 3),
        "max_ms": round(ordered[-1], 3),
        "p95_ms": round(ordered[rank - 1], 3),
    }


def build_audit(
    scenarios: List[Dict[str, Any]],
    *,
    target: str,
    manifest_path: Optional[str] = None,
    manifest_name: Optional[str] = None,
    agent: Optional[Dict[str, Any]] = None,
    rpc_timeout: Optional[float] = None,
    max_duration: Optional[float] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    duration_ms: float = 0.0,
    exit_reason: str = STATUS_OK,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble the ``ecp_audit.json`` payload from collected scenario records."""
    scenario_records: List[Dict[str, Any]] = []
    durations: List[float] = []
    usages: List[Optional[Dict[str, Any]]] = []

    steps_planned = 0
    steps_executed = 0
    steps_failed = 0
    steps_skipped = 0
    checks_passed = 0
    checks_total = 0

    for scenario in scenarios:
        step_records: List[Dict[str, Any]] = []
        scenario_duration = 0.0

        for index, step in enumerate(scenario.get("steps", []), start=1):
            status = step.get("status", STATUS_OK)
            checks = step.get("checks", []) or []
            passed = sum(1 for check in checks if check.get("passed"))
            step_duration = float(step.get("duration_ms", 0.0) or 0.0)

            steps_planned += 1
            checks_total += len(checks)
            checks_passed += passed
            scenario_duration += step_duration

            if status == STATUS_OK:
                steps_executed += 1
                durations.append(step_duration)
                usages.append(step.get("usage"))
            elif status == STATUS_SKIPPED:
                steps_skipped += 1
            else:
                steps_failed += 1

            step_records.append(
                {
                    "index": index,
                    "input": step.get("input"),
                    "status": status,
                    "exit_reason": step.get("exit_reason", STATUS_OK),
                    "duration_ms": round(step_duration, 3),
                    "usage": step.get("usage"),
                    "tool_calls": len(step.get("tool_calls") or []),
                    "checks_passed": passed,
                    "checks_total": len(checks),
                    "error": step.get("error"),
                }
            )

        scenario_records.append(
            {
                "name": scenario.get("name"),
                "status": scenario.get("status", STATUS_OK),
                "exit_reason": scenario.get("exit_reason", STATUS_OK),
                "duration_ms": round(scenario_duration, 3),
                "steps": step_records,
            }
        )

    return {
        "audit_version": AUDIT_VERSION,
        "run_id": run_id or str(uuid.uuid4()),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": round(duration_ms, 3),
        "exit_reason": exit_reason,
        "runtime": {
            "name": "ecp-runtime",
            "version": runtime_version(),
            "python": platform.python_version(),
            "platform": sys.platform,
        },
        "manifest": {
            "path": manifest_path,
            "name": manifest_name,
            "digest": manifest_digest(manifest_path),
            "target": target,
        },
        "agent": agent or {},
        "limits": {
            "rpc_timeout_s": rpc_timeout,
            "max_duration_s": max_duration,
        },
        "totals": {
            "scenarios": len(scenario_records),
            "steps_planned": steps_planned,
            "steps_executed": steps_executed,
            "steps_failed": steps_failed,
            "steps_skipped": steps_skipped,
            "checks_passed": checks_passed,
            "checks_total": checks_total,
            "checks_failed": max(checks_total - checks_passed, 0),
        },
        "latency": latency_summary(durations),
        "usage": merge_usage(usages),
        "scenarios": scenario_records,
    }
