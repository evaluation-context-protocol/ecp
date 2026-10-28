"""
ECPSession and the evaluator bridges, against a real stdio agent process.

The agent below speaks raw JSON-RPC with no SDK, so these tests exercise exactly
what an evaluator sees over the wire.
"""

import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.integrations import promptfoo  # noqa: E402
from ecp_runtime.session import ECPSession  # noqa: E402

AGENT = textwrap.dedent(
    """
    import json, sys
    CAPS = json.loads(sys.argv[1])
    for line in sys.stdin:
        req = json.loads(line)
        if req["method"] == "agent/initialize":
            result = {"name": "Wire", "protocol_version": "1.0", "capabilities": CAPS}
        elif req["method"] == "agent/step":
            text = req["params"]["input"]
            calls = [{"name": "issue_refund", "arguments": {"order_id": "C300"}}] if "refund" in text else []
            result = {"status": "done", "public_output": "echo: " + text,
                      "tool_calls": calls, "evaluation_context": "checked"}
        else:
            result = {"status": "reset"}
        print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), flush=True)
    """
)


class _AgentScript(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "agent.py"
        self.path.write_text(AGENT, encoding="utf-8")

    def tearDown(self):
        self.dir.cleanup()

    def target(self, capabilities):
        # The command is run through a shell; quote the JSON argument for it.
        caps = json.dumps(json.dumps(capabilities))
        return f'"{sys.executable}" "{self.path}" {caps}'


class SessionTests(_AgentScript):
    def test_step_returns_reply_and_tool_calls(self):
        with ECPSession(self.target({"tool_calls": {}})) as agent:
            self.assertEqual(agent.agent_info["name"], "Wire")
            step = agent.step("refund C300 now")
        self.assertEqual(step.public_output, "echo: refund C300 now")
        self.assertEqual([c["name"] for c in step.tool_calls], ["issue_refund"])
        self.assertTrue(step.tool_calls_declared)

    def test_undeclared_tool_calls_are_flagged(self):
        with ECPSession(self.target({})) as agent:
            step = agent.step("hello")
        self.assertEqual(step.tool_calls, [])
        self.assertFalse(step.tool_calls_declared)


class PromptfooProviderTests(_AgentScript):
    def test_reply_is_output_and_actions_are_metadata(self):
        resp = promptfoo.call_api("refund C300 now", {"config": {"target": self.target({"tool_calls": {}})}})
        self.assertEqual(resp["output"], "echo: refund C300 now")
        self.assertEqual(resp["metadata"]["tool_names"], ["issue_refund"])
        self.assertTrue(resp["metadata"]["tool_calls_declared"])

    def test_missing_target_is_an_error_not_a_crash(self):
        self.assertIn("config.target", promptfoo.call_api("hi", {"config": {}})["error"])

    def test_agent_that_fails_to_start_is_reported(self):
        resp = promptfoo.call_api("hi", {"config": {"target": f'"{sys.executable}" -c "raise SystemExit(3)"'}})
        self.assertIn("error", resp)


@unittest.skipUnless(importlib.util.find_spec("deepeval"), "deepeval not installed")
class DeepEvalBridgeTests(_AgentScript):
    def test_step_maps_to_test_case(self):
        from ecp_runtime.integrations.deepeval import test_cases

        case = test_cases(self.target({"tool_calls": {}}), ["refund C300 now"])[0]
        self.assertEqual(case.actual_output, "echo: refund C300 now")
        self.assertEqual([t.name for t in case.tools_called], ["issue_refund"])
        self.assertEqual(case.tools_called[0].input_parameters, {"order_id": "C300"})

    def test_refuses_agent_that_does_not_report_tool_calls(self):
        from ecp_runtime.integrations.deepeval import UnreportedToolCalls, test_cases

        with self.assertRaises(UnreportedToolCalls):
            test_cases(self.target({}), ["hello"])
        case = test_cases(self.target({}), ["hello"], allow_unreported_tools=True)[0]
        self.assertEqual(case.tools_called, [])


if __name__ == "__main__":
    unittest.main()
