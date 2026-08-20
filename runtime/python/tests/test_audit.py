import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.audit import (
    build_audit,
    latency_summary,
    manifest_digest,
    merge_usage,
    utc_now,
)


def _step(status="ok", duration_ms=10.0, checks=None, usage=None, **extra):
    record = {
        "input": "hi",
        "status": status,
        "exit_reason": status if status != "ok" else "ok",
        "duration_ms": duration_ms,
        "usage": usage,
        "tool_calls": [],
        "checks": checks if checks is not None else [{"passed": True}],
        "error": None,
    }
    record.update(extra)
    return record


class UsageMergeTests(unittest.TestCase):
    def test_returns_none_when_nothing_reported(self) -> None:
        self.assertIsNone(merge_usage([None, None, {}]))

    def test_sums_fields_and_derives_total(self) -> None:
        merged = merge_usage(
            [{"input_tokens": 10, "output_tokens": 3}, {"input_tokens": 5, "output_tokens": 2}]
        )
        self.assertEqual(merged, {"input_tokens": 15, "output_tokens": 5, "total_tokens": 20})

    def test_keeps_reported_total_without_recomputing(self) -> None:
        merged = merge_usage([{"input_tokens": 1, "output_tokens": 1, "total_tokens": 9}])
        self.assertEqual(merged["total_tokens"], 9)

    def test_ignores_non_integer_and_boolean_values(self) -> None:
        self.assertIsNone(merge_usage([{"input_tokens": "12"}, {"output_tokens": True}]))


class LatencySummaryTests(unittest.TestCase):
    def test_empty_input_yields_zeros(self) -> None:
        self.assertEqual(
            latency_summary([]),
            {"total_ms": 0.0, "mean_ms": 0.0, "max_ms": 0.0, "p95_ms": 0.0},
        )

    def test_aggregates_by_nearest_rank(self) -> None:
        summary = latency_summary([float(n) for n in range(1, 101)])
        self.assertEqual(summary["max_ms"], 100.0)
        self.assertEqual(summary["p95_ms"], 95.0)
        self.assertEqual(summary["mean_ms"], 50.5)
        self.assertEqual(summary["total_ms"], 5050.0)

    def test_single_sample(self) -> None:
        summary = latency_summary([7.5])
        self.assertEqual(summary["p95_ms"], 7.5)
        self.assertEqual(summary["max_ms"], 7.5)


class ManifestDigestTests(unittest.TestCase):
    def test_digest_is_stable_and_prefixed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "manifest.yaml"
            path.write_text("name: demo\n", encoding="utf-8")
            first = manifest_digest(str(path))
            self.assertTrue(first.startswith("sha256:"))
            self.assertEqual(first, manifest_digest(str(path)))

            path.write_text("name: changed\n", encoding="utf-8")
            self.assertNotEqual(first, manifest_digest(str(path)))

    def test_missing_paths_are_tolerated(self) -> None:
        self.assertIsNone(manifest_digest(None))
        self.assertIsNone(manifest_digest("does-not-exist.yaml"))


class BuildAuditTests(unittest.TestCase):
    def test_totals_separate_executed_failed_and_skipped(self) -> None:
        scenarios = [
            {
                "name": "S1",
                "status": "failed",
                "exit_reason": "timeout",
                "steps": [
                    _step("ok", 12.0, usage={"input_tokens": 4, "output_tokens": 1}),
                    _step("failed", 30.0, checks=[{"passed": False}]),
                    _step("skipped", 0.0, checks=[{"passed": False}]),
                ],
            }
        ]

        audit = build_audit(scenarios, target="python agent.py", exit_reason="timeout")

        totals = audit["totals"]
        self.assertEqual(totals["scenarios"], 1)
        self.assertEqual(totals["steps_planned"], 3)
        self.assertEqual(totals["steps_executed"], 1)
        self.assertEqual(totals["steps_failed"], 1)
        self.assertEqual(totals["steps_skipped"], 1)
        self.assertEqual(totals["checks_total"], 3)
        self.assertEqual(totals["checks_passed"], 1)
        self.assertEqual(totals["checks_failed"], 2)
        self.assertEqual(audit["exit_reason"], "timeout")

    def test_latency_and_usage_exclude_steps_that_never_ran(self) -> None:
        scenarios = [
            {
                "name": "S1",
                "status": "failed",
                "exit_reason": "timeout",
                "steps": [
                    _step("ok", 10.0, usage={"input_tokens": 4, "output_tokens": 1}),
                    # A timed-out step burns wall clock but must not skew latency stats.
                    _step("failed", 30000.0, checks=[{"passed": False}]),
                    _step("skipped", 0.0, checks=[{"passed": False}], usage={"input_tokens": 999}),
                ],
            }
        ]

        audit = build_audit(scenarios, target="t")

        self.assertEqual(audit["latency"]["max_ms"], 10.0)
        self.assertEqual(audit["usage"], {"input_tokens": 4, "output_tokens": 1, "total_tokens": 5})

    def test_steps_are_indexed_from_one_and_scenario_duration_sums_steps(self) -> None:
        scenarios = [
            {
                "name": "S1",
                "status": "ok",
                "exit_reason": "ok",
                "steps": [_step("ok", 5.0), _step("ok", 7.5)],
            }
        ]

        audit = build_audit(scenarios, target="t")

        indices = [step["index"] for step in audit["scenarios"][0]["steps"]]
        self.assertEqual(indices, [1, 2])
        self.assertEqual(audit["scenarios"][0]["duration_ms"], 12.5)

    def test_metadata_round_trip(self) -> None:
        audit = build_audit(
            [],
            target="http://127.0.0.1:8765/ecp",
            manifest_name="Demo",
            agent={"name": "SupportAgent", "capabilities": {}},
            rpc_timeout=30.0,
            max_duration=120.0,
            started_at=utc_now(),
            duration_ms=42.0,
            run_id="fixed-run-id",
        )

        self.assertEqual(audit["audit_version"], "1")
        self.assertEqual(audit["run_id"], "fixed-run-id")
        self.assertEqual(audit["manifest"]["target"], "http://127.0.0.1:8765/ecp")
        self.assertEqual(audit["manifest"]["name"], "Demo")
        self.assertIsNone(audit["manifest"]["digest"])
        self.assertEqual(audit["agent"]["name"], "SupportAgent")
        self.assertEqual(audit["limits"], {"rpc_timeout_s": 30.0, "max_duration_s": 120.0})
        self.assertEqual(audit["duration_ms"], 42.0)
        self.assertIsNone(audit["usage"])
        self.assertIn("version", audit["runtime"])

    def test_timestamps_are_utc_iso8601(self) -> None:
        stamp = utc_now()
        self.assertTrue(stamp.endswith("Z"))
        self.assertIn("T", stamp)


if __name__ == "__main__":
    unittest.main()
