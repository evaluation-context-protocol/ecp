import sys
import unittest
from pathlib import Path

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.conformance import (
    build_conformance_report,
    conformance_check,
    validate_initialize_result,
    validate_reset_result,
    validate_rpc_response,
    validate_step_result,
)


class ConformanceTests(unittest.TestCase):
    def test_valid_step_result(self) -> None:
        result = {
            "status": "done",
            "public_output": "ok",
            "evaluation_context": "verified",
            "tool_calls": [{"name": "lookup", "arguments": {"id": 1}}],
            "logs": "complete",
        }

        self.assertIs(validate_step_result(result), result)

    def test_initialize_contract(self) -> None:
        result = {"name": "agent", "capabilities": {}}
        self.assertIs(validate_initialize_result(result), result)

        with self.assertRaisesRegex(ValueError, "capabilities"):
            validate_initialize_result({"name": "agent"})

    def test_reset_contract(self) -> None:
        self.assertTrue(validate_reset_result(True))
        with self.assertRaisesRegex(ValueError, "must be true"):
            validate_reset_result(None)

    def test_invalid_status_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "status"):
            validate_step_result({"status": "complete"})

    def test_invalid_tool_call_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "name"):
            validate_step_result({"status": "done", "tool_calls": [{"arguments": {}}]})

    def test_rpc_envelope_requires_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "include id"):
            validate_rpc_response({"jsonrpc": "2.0", "result": {}}, "agent/initialize")

    def test_rpc_envelope_rejects_result_and_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "both result and error"):
            validate_rpc_response(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {},
                    "error": {"code": -32000, "message": "failure"},
                },
                "agent/initialize",
            )

    def test_report_has_stable_counts(self) -> None:
        checks = [
            conformance_check(
                "initialize",
                "agent/initialize",
                {"jsonrpc": "2.0", "id": 1, "result": {}},
            ),
            conformance_check(
                "step",
                "agent/step",
                {"jsonrpc": "2.0", "id": 2, "result": {"status": "invalid"}},
                result_validator=validate_step_result,
            ),
        ]

        report = build_conformance_report("python agent.py", checks)

        self.assertFalse(report["conformant"])
        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["total"], 2)


if __name__ == "__main__":
    unittest.main()
