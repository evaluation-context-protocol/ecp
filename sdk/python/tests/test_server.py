import json
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib import error, request

SDK_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

import ecp.server as server
from ecp import Result, agent, on_step


@agent(name="HTTPTestAgent")
class HTTPTestAgent:
    @on_step
    def step(self, user_input: str) -> Result:
        return Result(public_output=f"echo: {user_input}", evaluation_context="echoed input")


class StreamableHTTPServerTests(unittest.TestCase):
    def setUp(self) -> None:
        server._CURRENT_AGENT_INSTANCE = HTTPTestAgent()
        self.httpd = server._build_http_server(
            host="127.0.0.1",
            port=0,
            path="/ecp",
            allowed_origins=("http://client.example",),
        )
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.httpd.server_port}/ecp"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.thread.join(timeout=2)
        self.httpd.server_close()

    def _post(self, payload, headers=None):
        req = request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                **(headers or {}),
            },
        )
        with request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else None, resp.headers

    def test_post_json_rpc_request_returns_json_response(self) -> None:
        status, body, headers = self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "agent/step",
                "params": {"input": "hello"},
            }
        )

        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("Content-Type", ""))
        self.assertEqual(body["result"]["public_output"], "echo: hello")
        self.assertEqual(body["result"]["evaluation_context"], "echoed input")

    def test_result_syncs_private_thought_alias(self) -> None:
        result = Result(public_output="ok", private_thought="legacy")

        self.assertEqual(result.evaluation_context, "legacy")

    def test_result_rejects_invalid_status(self) -> None:
        with self.assertRaisesRegex(ValueError, "status"):
            Result(status="complete", public_output="ok")

    def test_result_rejects_invalid_tool_call(self) -> None:
        with self.assertRaisesRegex(ValueError, "name"):
            Result(tool_calls=[{"arguments": {}}])

    def test_server_serializes_logs(self) -> None:
        result = Result(public_output="ok", logs="trace")

        with mock.patch.object(HTTPTestAgent, "step", return_value=result):
            status, body, _headers = self._post(
                {"jsonrpc": "2.0", "id": 1, "method": "agent/step", "params": {"input": "hello"}}
            )

        self.assertEqual(status, 200)
        self.assertEqual(body["result"]["logs"], "trace")

    def test_post_json_rpc_notification_returns_accepted(self) -> None:
        status, body, _headers = self._post(
            {"jsonrpc": "2.0", "method": "agent/initialize", "params": {}}
        )

        self.assertEqual(status, 202)
        self.assertIsNone(body)

    def test_get_endpoint_returns_method_not_allowed(self) -> None:
        req = request.Request(
            self.endpoint,
            method="GET",
            headers={"Accept": "text/event-stream"},
        )

        with self.assertRaises(error.HTTPError) as ctx:
            request.urlopen(req, timeout=5)

        self.assertEqual(ctx.exception.code, 405)

    def test_rejects_untrusted_origin(self) -> None:
        with self.assertRaises(error.HTTPError) as ctx:
            self._post(
                {"jsonrpc": "2.0", "id": 1, "method": "agent/initialize"},
                headers={"Origin": "http://evil.example"},
            )

        self.assertEqual(ctx.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
