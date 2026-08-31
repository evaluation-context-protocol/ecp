import json
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.errors import ECPTimeoutError
from ecp_runtime.manifest import StepConfig
from ecp_runtime.protocol import PROTOCOL_VERSION
from ecp_runtime.runner import (
    ECPRunner,
    HTTPAgentClient,
    _ensure_response_id,
    resolve_max_duration,
    resolve_rpc_timeout,
)


class RunnerTests(unittest.TestCase):
    def _manifest(self, step_count=1, scenario_count=1):
        scenarios = []
        for scenario_idx in range(scenario_count):
            steps = [StepConfig(input=f"hello {i}", graders=[]) for i in range(step_count)]
            name = "Scenario A" if scenario_idx == 0 else f"Scenario {chr(65 + scenario_idx)}"
            scenarios.append(SimpleNamespace(name=name, steps=steps))
        return SimpleNamespace(target="python agent.py", name="Test Manifest", scenarios=scenarios)

    def test_runner_collects_results(self) -> None:
        initialize_params = []

        class FakeAgentProcess:
            def __init__(self, command, rpc_timeout=30.0):
                self.command = command
                self.rpc_timeout = rpc_timeout

            def start(self):
                return None

            def stop(self):
                return None

            def send_rpc(self, method, params=None):
                if method == "agent/initialize":
                    initialize_params.append(params)
                    return {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": {
                            "name": "x",
                            "protocol_version": PROTOCOL_VERSION,
                            "capabilities": {},
                        },
                    }
                return {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {"status": "done", "public_output": "ok", "evaluation_context": "checked"},
                }

        with mock.patch("ecp_runtime.runner.AgentProcess", FakeAgentProcess):
            output = ECPRunner(self._manifest()).run_scenarios()

        self.assertEqual(output["total"], 0)
        self.assertEqual(len(output["scenarios"]), 1)
        self.assertEqual(output["scenarios"][0]["name"], "Scenario A")
        self.assertEqual(output["scenarios"][0]["steps"][0]["evaluation_context"], "checked")
        self.assertEqual(
            initialize_params,
            [{"protocol_version": PROTOCOL_VERSION, "config": {}}],
        )

    def test_legacy_agent_warns_once_and_records_legacy_version(self) -> None:
        class LegacyAgentProcess:
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
                        "result": {"name": "LegacyAgent", "capabilities": {}},
                    }
                return {"jsonrpc": "2.0", "id": 2, "result": {"status": "done"}}

        with mock.patch("ecp_runtime.runner.AgentProcess", LegacyAgentProcess):
            with self.assertLogs("ecp_runtime.runner", level="WARNING") as captured:
                output = ECPRunner(self._manifest(scenario_count=2)).run_scenarios()

        warnings = [line for line in captured.output if "legacy protocol 0.1" in line]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(output["audit"]["agent"]["protocol_version"], "0.1")

    def test_legacy_warning_is_emitted_once_for_each_reused_runner_run(self) -> None:
        class LegacyAgentProcess:
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
                        "result": {"name": "LegacyAgent", "capabilities": {}},
                    }
                return {"jsonrpc": "2.0", "id": 2, "result": {"status": "done"}}

        runner = ECPRunner(self._manifest())
        with mock.patch("ecp_runtime.runner.AgentProcess", LegacyAgentProcess):
            with self.assertLogs("ecp_runtime.runner", level="WARNING") as captured:
                runner.run_scenarios()
                runner.run_scenarios()

        warnings = [line for line in captured.output if "legacy protocol 0.1" in line]
        self.assertEqual(len(warnings), 2)

    def test_major_version_mismatch_aborts_before_any_step(self) -> None:
        instances = []

        class IncompatibleAgentProcess:
            def __init__(self, command, rpc_timeout=30.0):
                self.step_calls = 0
                instances.append(self)

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
                            "name": "FutureAgent",
                            "protocol_version": "2.0",
                            "capabilities": {},
                        },
                    }
                self.step_calls += 1
                raise AssertionError("agent/step must not run after a version mismatch")

        with mock.patch("ecp_runtime.runner.AgentProcess", IncompatibleAgentProcess):
            output = ECPRunner(self._manifest(scenario_count=2)).run_scenarios()

        self.assertEqual(output["exit_reason"], "protocol_error")
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].step_calls, 0)
        self.assertTrue(
            all(step["status"] == "skipped" for scenario in output["scenarios"] for step in scenario["steps"])
        )
        self.assertIn("-32001", output["scenarios"][0]["steps"][0]["error"])

    def test_version_unsupported_rpc_error_aborts_before_any_step(self) -> None:
        class RejectingAgentProcess:
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
                        "error": {"code": -32001, "message": "VERSION_UNSUPPORTED"},
                    }
                raise AssertionError("agent/step must not run after a version mismatch")

        with mock.patch("ecp_runtime.runner.AgentProcess", RejectingAgentProcess):
            output = ECPRunner(self._manifest(scenario_count=2)).run_scenarios()

        self.assertEqual(output["exit_reason"], "protocol_error")
        self.assertIn("-32001", output["scenarios"][0]["steps"][0]["error"])

    def test_rpc_error_fails_the_step_instead_of_aborting_the_run(self) -> None:
        class FakeAgentProcess:
            def __init__(self, command, rpc_timeout=30.0):
                self.command = command
                self.rpc_timeout = rpc_timeout

            def start(self):
                return None

            def stop(self):
                return None

            def send_rpc(self, method, params=None):
                if method == "agent/initialize":
                    return {"jsonrpc": "2.0", "id": 1, "result": {"name": "x", "capabilities": {}}}
                return {"jsonrpc": "2.0", "id": 2, "error": {"code": -32000, "message": "boom"}}

        with mock.patch("ecp_runtime.runner.AgentProcess", FakeAgentProcess):
            output = ECPRunner(self._manifest()).run_scenarios()

        self.assertEqual(output["exit_reason"], "agent_error")
        step = output["scenarios"][0]["steps"][0]
        self.assertEqual(step["status"], "failed")
        self.assertEqual(step["exit_reason"], "agent_error")
        # The failure must still be counted, or CI reads a broken run as a pass.
        self.assertEqual(output["total"], 1)
        self.assertEqual(output["passed"], 0)
        self.assertIn("Scenario A", step["error"])
        self.assertIn("step=1", step["error"])
        self.assertIn("boom", step["error"])

    def test_invalid_initialize_result_fails_only_that_scenario(self) -> None:
        class FakeAgentProcess:
            def __init__(self, command, rpc_timeout=30.0):
                pass

            def start(self):
                return None

            def stop(self):
                return None

            def send_rpc(self, method, params=None):
                return {"jsonrpc": "2.0", "id": 1, "result": {"name": "missing-capabilities"}}

        with mock.patch("ecp_runtime.runner.AgentProcess", FakeAgentProcess):
            output = ECPRunner(self._manifest(scenario_count=2)).run_scenarios()

        self.assertEqual(output["exit_reason"], "protocol_error")
        # Both scenarios are attempted; neither aborts the run.
        self.assertEqual(len(output["scenarios"]), 2)
        for scenario in output["scenarios"]:
            self.assertEqual(scenario["status"], "failed")
            self.assertEqual(scenario["steps"][0]["status"], "skipped")
            self.assertIn("Invalid agent/initialize result", scenario["steps"][0]["error"])

    def test_step_failure_skips_remaining_steps_in_that_scenario(self) -> None:
        class FakeAgentProcess:
            def __init__(self, command, rpc_timeout=30.0):
                self.calls = 0

            def start(self):
                return None

            def stop(self):
                return None

            def send_rpc(self, method, params=None):
                if method == "agent/initialize":
                    return {"jsonrpc": "2.0", "id": 1, "result": {"name": "x", "capabilities": {}}}
                self.calls += 1
                if self.calls == 1:
                    return {"jsonrpc": "2.0", "id": 2, "result": {"status": "done", "public_output": "ok"}}
                raise ECPTimeoutError("Agent response timed out after 0.1s")

        with mock.patch("ecp_runtime.runner.AgentProcess", FakeAgentProcess):
            output = ECPRunner(self._manifest(step_count=4)).run_scenarios()

        statuses = [step["status"] for step in output["scenarios"][0]["steps"]]
        self.assertEqual(statuses, ["ok", "failed", "skipped", "skipped"])
        self.assertEqual(output["exit_reason"], "timeout")

        totals = output["audit"]["totals"]
        self.assertEqual(totals["steps_planned"], 4)
        self.assertEqual(totals["steps_executed"], 1)
        self.assertEqual(totals["steps_failed"], 1)
        self.assertEqual(totals["steps_skipped"], 2)

    def test_runner_uses_http_client_for_url_target(self) -> None:
        runner = ECPRunner(SimpleNamespace(target="http://127.0.0.1:8765/ecp", scenarios=[]))

        agent = runner._create_agent(runner.manifest.target, rpc_timeout=12.0)

        self.assertIsInstance(agent, HTTPAgentClient)
        self.assertEqual(agent.endpoint, "http://127.0.0.1:8765/ecp")
        self.assertEqual(agent.rpc_timeout, 12.0)

    def test_runner_passes_explicit_timeout_to_agent(self) -> None:
        observed = {}

        class FakeAgentProcess:
            def __init__(self, command, rpc_timeout=30.0):
                observed["timeout"] = rpc_timeout

            def start(self):
                return None

            def stop(self):
                return None

            def send_rpc(self, method, params=None):
                if method == "agent/initialize":
                    return {"jsonrpc": "2.0", "id": 1, "result": {"name": "x", "capabilities": {}}}
                return {"jsonrpc": "2.0", "id": 2, "result": {"status": "done"}}

        with mock.patch("ecp_runtime.runner.AgentProcess", FakeAgentProcess):
            ECPRunner(self._manifest(), rpc_timeout=4.25).run_scenarios()

        self.assertEqual(observed["timeout"], 4.25)

    def test_transport_timeout_includes_method_and_step_context(self) -> None:
        class FakeAgentProcess:
            def __init__(self, command, rpc_timeout=30.0):
                pass

            def start(self):
                return None

            def stop(self):
                return None

            def send_rpc(self, method, params=None):
                if method == "agent/initialize":
                    return {"jsonrpc": "2.0", "id": 1, "result": {"name": "x", "capabilities": {}}}
                raise ECPTimeoutError("Agent response timed out after 0.1s")

        with mock.patch("ecp_runtime.runner.AgentProcess", FakeAgentProcess):
            output = ECPRunner(self._manifest(), rpc_timeout=0.1).run_scenarios()

        step = output["scenarios"][0]["steps"][0]
        self.assertEqual(step["exit_reason"], "timeout")
        message = step["error"]
        self.assertIn("agent/step", message)
        self.assertIn("Scenario A", message)
        self.assertIn("step=1", message)
        self.assertIn("timed out", message)

    def test_agent_that_fails_to_start_does_not_abort_the_run(self) -> None:
        class ExplodingAgentProcess:
            def __init__(self, command, rpc_timeout=30.0):
                pass

            def start(self):
                raise OSError("cannot spawn agent")

            def stop(self):
                return None

            def send_rpc(self, method, params=None):
                raise AssertionError("should not be reached")

        with mock.patch("ecp_runtime.runner.AgentProcess", ExplodingAgentProcess):
            output = ECPRunner(self._manifest()).run_scenarios()

        self.assertEqual(output["exit_reason"], "transport_error")
        self.assertEqual(output["scenarios"][0]["steps"][0]["status"], "skipped")
        self.assertEqual(output["passed"], 0)
        self.assertEqual(output["total"], 1)

    def test_max_duration_stops_the_run_and_marks_remaining_work_skipped(self) -> None:
        class SlowAgentProcess:
            def __init__(self, command, rpc_timeout=30.0):
                pass

            def start(self):
                return None

            def stop(self):
                return None

            def send_rpc(self, method, params=None):
                if method == "agent/initialize":
                    return {"jsonrpc": "2.0", "id": 1, "result": {"name": "x", "capabilities": {}}}
                time.sleep(0.05)
                return {"jsonrpc": "2.0", "id": 2, "result": {"status": "done", "public_output": "ok"}}

        with mock.patch("ecp_runtime.runner.AgentProcess", SlowAgentProcess):
            output = ECPRunner(
                self._manifest(step_count=6, scenario_count=2), max_duration=0.06
            ).run_scenarios()

        self.assertEqual(output["exit_reason"], "max_duration_exceeded")
        statuses = [step["status"] for step in output["scenarios"][0]["steps"]]
        self.assertIn("skipped", statuses)
        # The second scenario never starts, but is still accounted for.
        self.assertEqual(output["scenarios"][1]["exit_reason"], "max_duration_exceeded")
        self.assertTrue(all(s["status"] == "skipped" for s in output["scenarios"][1]["steps"]))
        self.assertEqual(output["passed"], 0)

    def test_successful_run_records_latency_usage_and_agent_metadata(self) -> None:
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
                            "name": "SupportAgent",
                            "protocol_version": PROTOCOL_VERSION,
                            "capabilities": {},
                        },
                    }
                return {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "status": "done",
                        "public_output": "ok",
                        "usage": {"input_tokens": 10, "output_tokens": 4},
                    },
                }

        with mock.patch("ecp_runtime.runner.AgentProcess", FakeAgentProcess):
            output = ECPRunner(self._manifest(step_count=2)).run_scenarios()

        audit = output["audit"]
        self.assertEqual(output["exit_reason"], "ok")
        self.assertEqual(audit["agent"]["name"], "SupportAgent")
        self.assertEqual(audit["agent"]["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(audit["manifest"]["target"], "python agent.py")
        self.assertEqual(audit["usage"], {"input_tokens": 20, "output_tokens": 8, "total_tokens": 28})
        self.assertEqual(audit["totals"]["steps_executed"], 2)
        self.assertGreaterEqual(audit["latency"]["total_ms"], 0.0)
        self.assertEqual(len(audit["scenarios"][0]["steps"]), 2)
        self.assertEqual(audit["scenarios"][0]["steps"][0]["index"], 1)

    def test_max_duration_resolution_validates_environment(self) -> None:
        self.assertIsNone(resolve_max_duration())
        self.assertEqual(resolve_max_duration(12), 12.0)

        with mock.patch.dict("os.environ", {"ECP_MAX_DURATION": "45"}):
            self.assertEqual(resolve_max_duration(), 45.0)
            self.assertEqual(resolve_max_duration(2), 2.0)

        for invalid in ("invalid", "0", "-1", "inf", "nan"):
            with self.subTest(invalid=invalid):
                with mock.patch.dict("os.environ", {"ECP_MAX_DURATION": invalid}):
                    with self.assertRaisesRegex(ValueError, "positive"):
                        resolve_max_duration()

    def test_timeout_resolution_prefers_explicit_value_and_validates_environment(self) -> None:
        with mock.patch.dict("os.environ", {"ECP_RPC_TIMEOUT": "8.5"}):
            self.assertEqual(resolve_rpc_timeout(), 8.5)
            self.assertEqual(resolve_rpc_timeout(2), 2.0)

        for invalid in ("invalid", "0", "-1", "inf", "nan"):
            with self.subTest(invalid=invalid):
                with mock.patch.dict("os.environ", {"ECP_RPC_TIMEOUT": invalid}):
                    with self.assertRaisesRegex(ValueError, "positive"):
                        resolve_rpc_timeout()

    def test_http_agent_client_posts_json_rpc(self) -> None:
        class FakeResponse:
            headers = {"Content-Type": "application/json; charset=utf-8"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b'{"jsonrpc":"2.0","id":1,"result":{"ok":true}}'

        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["timeout"] = timeout
            captured["body"] = req.data
            captured["accept"] = req.headers.get("Accept")
            request_id = json.loads(req.data.decode("utf-8"))["id"]
            FakeResponse.read = lambda self: json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "result": {"ok": True}}
            ).encode("utf-8")
            return FakeResponse()

        with mock.patch("ecp_runtime.runner.request.urlopen", fake_urlopen):
            response = HTTPAgentClient("http://agent.test/ecp", rpc_timeout=3).send_rpc(
                "agent/step", {"input": "hi"}
            )

        self.assertEqual(response["result"]["ok"], True)
        self.assertEqual(captured["url"], "http://agent.test/ecp")
        self.assertEqual(captured["timeout"], 3)
        self.assertIn("application/json", captured["accept"])
        body = captured["body"].decode("utf-8")
        self.assertIn('"method": "agent/step"', body)
        self.assertIn('"input": "hi"', body)

    def test_response_id_must_match_request(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "id mismatch"):
            _ensure_response_id({"jsonrpc": "2.0", "id": 2, "result": {}}, 1)

        with self.assertRaisesRegex(RuntimeError, "id mismatch"):
            _ensure_response_id({"jsonrpc": "2.0", "id": True, "result": {}}, 1)


if __name__ == "__main__":
    unittest.main()
