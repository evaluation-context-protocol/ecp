"""
Docstring for runtime.python.src.ecp_runtime.runner

Simplified Version. V0.1
AsyncIO Pending
"""

import json
import logging
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib import error, request
from urllib.parse import urlparse

from .graders import evaluate_step

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    status: str
    public_output: Optional[str] = None
    private_thought: Optional[str] = None
    logs: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class AgentProcess:
    """Manages the lifecycle of the Agent Child Process."""

    def __init__(self, command: str, rpc_timeout: float = 30.0):
        self.command = command
        self.rpc_timeout = rpc_timeout
        self.process = None

    def start(self):
        # Launch the agent and connect pipes to stdio
        self.process = subprocess.Popen(
            self.command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1 # Line buffered
        )

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def send_rpc(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Sends a JSON-RPC request and waits for the response."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Agent process is not running")
        if not params:
            params = {}

        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000)
        }

        # Write to Agent's STDIN
        json_str = json.dumps(request)
        self.process.stdin.write(json_str + "\n")
        self.process.stdin.flush()

        return self._read_json_response()

    def _read_json_response(self) -> Dict[str, Any]:
        start_time = time.time()
        last_non_json = None

        while True:
            elapsed = time.time() - start_time
            remaining = max(self.rpc_timeout - elapsed, 0)
            if remaining <= 0:
                stderr = self._safe_read_stderr()
                raise RuntimeError(
                    f"Agent response timed out after {self.rpc_timeout:.1f}s. "
                    f"Last non-JSON line: {last_non_json}. Stderr: {stderr}"
                )

            response_line = self._readline_with_timeout(remaining)
            if response_line is None:
                stderr = self._safe_read_stderr()
                raise RuntimeError(
                    f"Agent response timed out after {self.rpc_timeout:.1f}s. "
                    f"Last non-JSON line: {last_non_json}. Stderr: {stderr}"
                )

            if response_line == "":
                stderr = self._safe_read_stderr()
                raise RuntimeError(f"Agent crashed or closed connection. Stderr: {stderr}")

            line = response_line.strip()
            if not line:
                continue

            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    return payload
                last_non_json = line
            except json.JSONDecodeError:
                last_non_json = line
                logger.warning("Agent emitted non-JSON stdout: %s", line)
                continue

    def _readline_with_timeout(self, timeout: float) -> Optional[str]:
        if not self.process or not self.process.stdout:
            return None

        q: queue.Queue = queue.Queue(maxsize=1)

        def _reader():
            try:
                q.put(self.process.stdout.readline())
            except Exception:
                q.put("")

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None

    def _safe_read_stderr(self) -> str:
        if not self.process or not self.process.stderr:
            return ""
        if self.process.poll() is None:
            return ""
        try:
            return self.process.stderr.read()
        except Exception:
            return ""


class HTTPAgentClient:
    """JSON-RPC client for ECP Streamable HTTP endpoints."""

    def __init__(self, endpoint: str, rpc_timeout: float = 30.0):
        self.endpoint = endpoint
        self.rpc_timeout = rpc_timeout

    def start(self):
        return None

    def stop(self):
        return None

    def send_rpc(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if not params:
            params = {}

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000),
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )

        try:
            with request.urlopen(req, timeout=self.rpc_timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"HTTP RPC failed: status={exc.code}, body={raw or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"HTTP RPC failed: {exc.reason}") from exc

        if "text/event-stream" in content_type:
            return self._parse_sse_response(raw)
        if not raw:
            raise RuntimeError("HTTP RPC response was empty")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RuntimeError("HTTP RPC response must be a JSON object")
        return payload

    def _parse_sse_response(self, raw: str) -> Dict[str, Any]:
        for event in raw.split("\n\n"):
            data_lines = []
            for line in event.splitlines():
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
            if not data_lines:
                continue
            payload = json.loads("\n".join(data_lines))
            if isinstance(payload, dict) and ("result" in payload or "error" in payload):
                return payload
        raise RuntimeError("SSE stream ended without a JSON-RPC response")


class ECPRunner:
    """The Orchestrator."""

    def __init__(self, manifest):
        self.manifest = manifest

    def run_scenarios(self):
        total_passed = 0
        total_checks = 0
        report_data: List[Dict[str, Any]] = []

        for scenario in self.manifest.scenarios:
            logger.info("Scenario: %s", scenario.name)

            rpc_timeout = float(os.environ.get("ECP_RPC_TIMEOUT", "30"))
            agent = self._create_agent(self.manifest.target, rpc_timeout=rpc_timeout)
            agent.start()

            try:
                init_resp = agent.send_rpc("agent/initialize", {"config": {}})
                self._ensure_rpc_success(init_resp, scenario.name, step_idx=None, method="agent/initialize")
                scenario_steps: List[Dict[str, Any]] = []

                for i, step in enumerate(scenario.steps):
                    # Execute
                    rpc_resp = agent.send_rpc("agent/step", {"input": step.input})
                    self._ensure_rpc_success(rpc_resp, scenario.name, step_idx=i + 1, method="agent/step")
                    result_data = rpc_resp.get("result", {})

                    # Map to internal object
                    step_result = StepResult(
                        status=result_data.get("status", "done"),
                        public_output=result_data.get("public_output"),
                        private_thought=result_data.get("private_thought"),
                        tool_calls=result_data.get("tool_calls") if isinstance(result_data.get("tool_calls"), list) else None
                    )

                    logger.info("Step %d: Input='%s'", i + 1, step.input)
                    logger.info("Output: %s", step_result.public_output)
                    if step_result.private_thought:
                        logger.debug("Thought: %s", step_result.private_thought)

                    checks = evaluate_step(step, step_result)

                    for check in checks:
                        total_checks += 1
                        status = "PASS" if check["passed"] else "FAIL"
                        logger.info("%s | %s on %s", status, check["type"], check["field"])

                        if check["type"] == "llm_judge" or not check["passed"]:
                            logger.info("Reason: %s", check["reasoning"])

                        if check["passed"]:
                            total_passed += 1

                    # Collect for HTML report
                    scenario_steps.append({
                        "input": step.input,
                        "output": step_result.public_output,
                        "checks": checks
                    })

            finally:
                agent.stop()

            # Append scenario block
            report_data.append({"name": scenario.name, "steps": scenario_steps})

        logger.info("Run Complete. Passed: %d/%d", total_passed, total_checks)

        # Return structured report data
        return {
            "passed": total_passed,
            "total": total_checks,
            "scenarios": report_data
        }

    def _create_agent(self, target: str, rpc_timeout: float):
        if _is_http_url(target):
            return HTTPAgentClient(target, rpc_timeout=rpc_timeout)
        return AgentProcess(target, rpc_timeout=rpc_timeout)

    def _ensure_rpc_success(
        self,
        rpc_resp: Dict[str, Any],
        scenario_name: str,
        step_idx: Optional[int],
        method: str,
    ) -> None:
        if "error" not in rpc_resp:
            return

        error = rpc_resp.get("error") or {}
        code = error.get("code")
        message = error.get("message", "Unknown JSON-RPC error")
        where = f"scenario='{scenario_name}'"
        if step_idx is not None:
            where += f", step={step_idx}"
        raise RuntimeError(
            f"RPC call failed ({method}) at {where}: code={code}, message={message}"
        )


def _is_http_url(target: str) -> bool:
    parsed = urlparse(target)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
