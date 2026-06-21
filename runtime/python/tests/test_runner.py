import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.manifest import StepConfig
from ecp_runtime.runner import ECPRunner, HTTPAgentClient, _ensure_response_id, resolve_rpc_timeout


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

    def test_runner_rejects_invalid_initialize_result(self) -> None:
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
            with self.assertRaisesRegex(RuntimeError, "Invalid agent/initialize result"):
                ECPRunner(self._manifest()).run_scenarios()

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
                raise RuntimeError("Agent response timed out after 0.1s")

        with mock.patch("ecp_runtime.runner.AgentProcess", FakeAgentProcess):
            with self.assertRaises(RuntimeError) as ctx:
                ECPRunner(self._manifest(), rpc_timeout=0.1).run_scenarios()

        message = str(ctx.exception)
        self.assertIn("agent/step", message)
        self.assertIn("Scenario A", message)
        self.assertIn("step=1", message)
        self.assertIn("timed out", message)

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
