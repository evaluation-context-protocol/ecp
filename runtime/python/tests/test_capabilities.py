"""
Agent capability declaration and the checks built on it.

The behaviour that matters is the default: an agent that declares nothing must
keep working. Every agent written before capabilities existed reports `{}`, and
the runtime cannot tell "cannot report tool calls" from "did not say so" — so
absence warns, and only a manifest opting in makes it fatal.
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.conformance import validate_initialize_result
from ecp_runtime.errors import ECPCapabilityRequired
from ecp_runtime.manifest import GraderConfig, StepConfig
from ecp_runtime.protocol import missing_capabilities, required_capabilities
from ecp_runtime.runner import ECPRunner


def _manifest(graders, *, require=False):
    step = StepConfig(input="hi", graders=graders)
    scenario = SimpleNamespace(name="S", steps=[step])
    return SimpleNamespace(
        target="python agent.py",
        name="M",
        require_capabilities=require,
        scenarios=[scenario],
    )


def _fake_agent(capabilities):
    class FakeAgentProcess:
        def __init__(self, command, rpc_timeout=30.0):
            pass

        def start(self):
            return None

        def stop(self):
            return None

        def send_rpc(self, method, params=None):
            if method == "agent/initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "name": "FakeAgent",
                        "protocol_version": "1.0",
                        "capabilities": capabilities,
                    },
                }
            return {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"status": "done", "public_output": "ok"},
            }

    return FakeAgentProcess


class RequiredCapabilityDerivationTests(unittest.TestCase):
    def test_tool_usage_grader_requires_tool_calls(self) -> None:
        needed = required_capabilities(
            _manifest([GraderConfig(type="tool_usage", tool_name="calc")])
        )

        self.assertIn("tool_calls", needed)

    def test_grader_on_evaluation_context_requires_that_capability(self) -> None:
        needed = required_capabilities(
            _manifest([
                GraderConfig(
                    type="text_match",
                    field="evaluation_context",
                    condition="contains",
                    value="checked",
                )
            ])
        )

        self.assertIn("evaluation_context", needed)

    def test_deprecated_private_thought_maps_to_evaluation_context(self) -> None:
        needed = required_capabilities(
            _manifest([
                GraderConfig(
                    type="text_match",
                    field="private_thought",
                    condition="contains",
                    value="x",
                )
            ])
        )

        self.assertIn("evaluation_context", needed)

    def test_plain_output_grader_requires_nothing(self) -> None:
        needed = required_capabilities(
            _manifest([GraderConfig(type="text_match", condition="contains", value="ok")])
        )

        self.assertEqual(needed, {})

    def test_requirements_name_the_grader_that_asked(self) -> None:
        """The error has to say why, or it is unactionable."""
        needed = required_capabilities(
            _manifest([GraderConfig(type="tool_usage", tool_name="calc")])
        )

        self.assertIn("tool_usage", needed["tool_calls"])


class MissingCapabilityTests(unittest.TestCase):
    def test_absence_is_reported_regardless_of_whether_anything_was_declared(self) -> None:
        needed = {"tool_calls": "a tool_usage grader"}

        self.assertEqual(missing_capabilities({}, needed), needed)
        self.assertEqual(missing_capabilities({"usage": {}}, needed), needed)
        self.assertEqual(missing_capabilities({"tool_calls": {}}, needed), {})


class RunnerCapabilityBehaviourTests(unittest.TestCase):
    def test_undeclared_capability_warns_but_the_run_proceeds(self) -> None:
        """The installed base declares nothing; it must keep working."""
        manifest = _manifest([GraderConfig(type="tool_usage", tool_name="calc")])

        with mock.patch("ecp_runtime.runner.AgentProcess", _fake_agent({})):
            with self.assertLogs("ecp_runtime.runner", level="WARNING") as logs:
                output = ECPRunner(manifest).run_scenarios()

        self.assertEqual(output["exit_reason"], "ok")
        self.assertEqual(output["scenarios"][0]["steps"][0]["status"], "ok")
        joined = " ".join(logs.output)
        self.assertIn("tool_calls", joined)
        self.assertIn("require_capabilities", joined)

    def test_warning_is_emitted_once_per_run_not_once_per_scenario(self) -> None:
        manifest = _manifest([GraderConfig(type="tool_usage", tool_name="calc")])
        manifest.scenarios = list(manifest.scenarios) * 3

        with mock.patch("ecp_runtime.runner.AgentProcess", _fake_agent({})):
            with self.assertLogs("ecp_runtime.runner", level="WARNING") as logs:
                ECPRunner(manifest).run_scenarios()

        undeclared = [line for line in logs.output if "does not declare" in line]
        self.assertEqual(len(undeclared), 1)

    def test_require_capabilities_aborts_before_any_step_runs(self) -> None:
        manifest = _manifest(
            [GraderConfig(type="tool_usage", tool_name="calc")], require=True
        )

        with mock.patch("ecp_runtime.runner.AgentProcess", _fake_agent({})):
            output = ECPRunner(manifest).run_scenarios()

        self.assertEqual(output["exit_reason"], "protocol_error")
        step = output["scenarios"][0]["steps"][0]
        self.assertEqual(step["status"], "skipped")
        self.assertIn("require_capabilities", step["error"])
        # The failure still counts, so CI cannot read it as a pass.
        self.assertEqual(output["passed"], 0)
        self.assertEqual(output["total"], 1)

    def test_declared_capability_satisfies_the_requirement(self) -> None:
        manifest = _manifest(
            [GraderConfig(type="tool_usage", tool_name="calc")], require=True
        )

        with mock.patch("ecp_runtime.runner.AgentProcess", _fake_agent({"tool_calls": {}})):
            output = ECPRunner(manifest).run_scenarios()

        self.assertEqual(output["exit_reason"], "ok")

    def test_capabilities_are_recorded_in_the_audit(self) -> None:
        manifest = _manifest([GraderConfig(type="text_match", condition="contains", value="ok")])

        with mock.patch(
            "ecp_runtime.runner.AgentProcess", _fake_agent({"usage": {}, "reset": {}})
        ):
            output = ECPRunner(manifest).run_scenarios()

        self.assertEqual(output["audit"]["agent"]["capabilities"], {"usage": {}, "reset": {}})


class CapabilityContractTests(unittest.TestCase):
    def test_capability_values_must_be_objects(self) -> None:
        with self.assertRaisesRegex(ValueError, "must map to an object"):
            validate_initialize_result(
                {"name": "a", "capabilities": {"tool_calls": True}}
            )

    def test_capability_names_must_be_non_empty_strings(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty strings"):
            validate_initialize_result({"name": "a", "capabilities": {"": {}}})

    def test_empty_and_populated_capability_sets_are_both_valid(self) -> None:
        for caps in ({}, {"tool_calls": {}}, {"multi_turn": {"max_turns": 20}}):
            with self.subTest(caps=caps):
                result = {"name": "a", "capabilities": caps}
                self.assertIs(validate_initialize_result(result), result)

    def test_unknown_capability_keys_are_accepted(self) -> None:
        """Ignoring unknown keys is what keeps minor versions additive."""
        result = {"name": "a", "capabilities": {"x-acme.tracing": {}}}

        self.assertIs(validate_initialize_result(result), result)

    def test_capability_error_is_a_protocol_error(self) -> None:
        self.assertEqual(ECPCapabilityRequired.exit_reason, "protocol_error")
        self.assertEqual(ECPCapabilityRequired.code, -32002)


if __name__ == "__main__":
    unittest.main()
