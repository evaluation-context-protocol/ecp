import sys
import unittest
from pathlib import Path

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.conformance import (
    build_conformance_report,
    conformance_check,
    validate_initialize_negotiation,
    validate_initialize_result,
    validate_reset_result,
    validate_rpc_response,
    validate_step_result,
)
from ecp_runtime.errors import ECPVersionUnsupported
from ecp_runtime.protocol import (
    LEGACY_PROTOCOL_VERSION,
    PROTOCOL_VERSION,
    initialize_params,
    negotiate_protocol_version,
    parse_protocol_version,
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

    def test_usage_is_optional_but_validated_when_present(self) -> None:
        for usage in (None, {}, {"input_tokens": 0}, {"input_tokens": 12, "output_tokens": 3}):
            with self.subTest(usage=usage):
                result = {"status": "done", "usage": usage}
                self.assertIs(validate_step_result(result), result)

    def test_invalid_usage_is_rejected(self) -> None:
        for usage, expected in (
            ("100", "must be an object"),
            ({"input_tokens": "12"}, "must be an integer"),
            ({"output_tokens": 1.5}, "must be an integer"),
            # bool is an int subclass in Python; the contract still rejects it.
            ({"total_tokens": True}, "must be an integer"),
            ({"input_tokens": -1}, "must not be negative"),
        ):
            with self.subTest(usage=usage):
                with self.assertRaisesRegex(ValueError, expected):
                    validate_step_result({"status": "done", "usage": usage})

    def test_initialize_contract(self) -> None:
        result = {"name": "agent", "capabilities": {}}
        self.assertIs(validate_initialize_result(result), result)

        versioned = {
            "name": "agent",
            "protocol_version": PROTOCOL_VERSION,
            "capabilities": {},
        }
        self.assertIs(validate_initialize_result(versioned), versioned)

        with self.assertRaisesRegex(ValueError, "capabilities"):
            validate_initialize_result({"name": "agent"})

        with self.assertRaisesRegex(ValueError, "MAJOR.MINOR"):
            validate_initialize_result(
                {"name": "agent", "protocol_version": "v1", "capabilities": {}}
            )

        with self.assertRaisesRegex(ValueError, "MAJOR.MINOR"):
            validate_initialize_result(
                {"name": "agent", "protocol_version": None, "capabilities": {}}
            )

    def test_protocol_version_negotiation(self) -> None:
        self.assertEqual(parse_protocol_version("12.34"), (12, 34))
        self.assertEqual(negotiate_protocol_version("1.0").version, PROTOCOL_VERSION)
        self.assertEqual(negotiate_protocol_version("1.7").version, PROTOCOL_VERSION)

        legacy = negotiate_protocol_version(None)
        self.assertTrue(legacy.legacy)
        self.assertEqual(legacy.version, LEGACY_PROTOCOL_VERSION)

        with self.assertRaisesRegex(ECPVersionUnsupported, "-32001"):
            negotiate_protocol_version("2.0")

        with self.assertRaisesRegex(ValueError, "-32001"):
            validate_initialize_negotiation(
                {"name": "agent", "protocol_version": "2.0", "capabilities": {}}
            )

    def test_initialize_params_advertise_runtime_protocol(self) -> None:
        self.assertEqual(
            initialize_params({"region": "test"}),
            {"protocol_version": PROTOCOL_VERSION, "config": {"region": "test"}},
        )

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
