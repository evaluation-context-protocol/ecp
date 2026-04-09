import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.manifest import StepConfig
from ecp_runtime.runner import ECPRunner


class RunnerTests(unittest.TestCase):
    def _manifest(self):
        step = StepConfig(input="hello", graders=[])
        scenario = SimpleNamespace(name="Scenario A", steps=[step])
        return SimpleNamespace(target="python agent.py", scenarios=[scenario])

    def test_runner_collects_results(self) -> None:
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
                return {"jsonrpc": "2.0", "id": 2, "result": {"status": "done", "public_output": "ok"}}

        with mock.patch("ecp_runtime.runner.AgentProcess", FakeAgentProcess):
            output = ECPRunner(self._manifest()).run_scenarios()

        self.assertEqual(output["total"], 0)
        self.assertEqual(len(output["scenarios"]), 1)
        self.assertEqual(output["scenarios"][0]["name"], "Scenario A")

    def test_runner_raises_on_rpc_error_with_context(self) -> None:
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
            with self.assertRaises(RuntimeError) as ctx:
                ECPRunner(self._manifest()).run_scenarios()

        msg = str(ctx.exception)
        self.assertIn("Scenario A", msg)
        self.assertIn("step=1", msg)
        self.assertIn("boom", msg)


if __name__ == "__main__":
    unittest.main()
