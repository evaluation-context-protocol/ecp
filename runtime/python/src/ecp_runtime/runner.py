"""
Docstring for runtime.python.src.ecp_runtime.runner

Simplified Version. V0.1
"""

import json
import logging
import math
import os
import queue
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request
from urllib.parse import urlparse

try:
    from .graders import evaluate_step
except ImportError:
    import os
    import sys
    sys.path.append(os.path.dirname(__file__))
    from graders import evaluate_step  # type: ignore
from . import audit as audit_module
from .conformance import (
    validate_initialize_result,
    validate_rpc_response,
    validate_step_result,
)
from .errors import (
    ECPAgentError,
    ECPBudgetExceeded,
    ECPExecutionError,
    ECPProtocolError,
    ECPTimeoutError,
    ECPTransportError,
    exit_reason_for,
)
from .graders import evaluate_step

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    status: str
    public_output: Optional[str] = None
    evaluation_context: Optional[str] = None
    private_thought: Optional[str] = None
    logs: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Optional[Dict[str, Any]] = None


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
            raise ECPTransportError("Agent process is not running")
        if not params:
            params = {}

        request_id = int(time.time() * 1000)
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id
        }

        # Write to Agent's STDIN
        json_str = json.dumps(request)
        self.process.stdin.write(json_str + "\n")
        self.process.stdin.flush()

        response = self._read_json_response()
        _ensure_response_id(response, request_id)
        return response

    def _read_json_response(self) -> Dict[str, Any]:
        start_time = time.time()
        last_non_json = None

        while True:
            elapsed = time.time() - start_time
            remaining = max(self.rpc_timeout - elapsed, 0)
            if remaining <= 0:
                stderr = self._safe_read_stderr()
                raise ECPTimeoutError(
                    f"Agent response timed out after {self.rpc_timeout:.1f}s. "
                    f"Last non-JSON line: {last_non_json}. Stderr: {stderr}"
                )

            response_line = self._readline_with_timeout(remaining)
            if response_line is None:
                stderr = self._safe_read_stderr()
                raise ECPTimeoutError(
                    f"Agent response timed out after {self.rpc_timeout:.1f}s. "
                    f"Last non-JSON line: {last_non_json}. Stderr: {stderr}"
                )

            if response_line == "":
                stderr = self._safe_read_stderr()
                raise ECPTransportError(f"Agent crashed or closed connection. Stderr: {stderr}")

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

        request_id = int(time.time() * 1000)
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id,
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
            raise ECPTransportError(
                f"HTTP RPC failed: status={exc.code}, body={raw or exc.reason}"
            ) from exc
        except error.URLError as exc:
            # urllib surfaces a read timeout as URLError wrapping socket.timeout.
            if isinstance(exc.reason, socket.timeout):
                raise ECPTimeoutError(
                    f"Agent response timed out after {self.rpc_timeout:.1f}s."
                ) from exc
            raise ECPTransportError(f"HTTP RPC failed: {exc.reason}") from exc
        except socket.timeout as exc:
            raise ECPTimeoutError(
                f"Agent response timed out after {self.rpc_timeout:.1f}s."
            ) from exc

        if "text/event-stream" in content_type:
            response = self._parse_sse_response(raw)
            _ensure_response_id(response, request_id)
            return response
        if not raw:
            raise ECPProtocolError("HTTP RPC response was empty")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ECPProtocolError(f"HTTP RPC response was not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ECPProtocolError("HTTP RPC response must be a JSON object")
        _ensure_response_id(payload, request_id)
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
        raise ECPProtocolError("SSE stream ended without a JSON-RPC response")


class ECPRunner:
    """The Orchestrator."""

    def __init__(
        self,
        manifest,
        rpc_timeout: Optional[float] = None,
        max_duration: Optional[float] = None,
        manifest_path: Optional[str] = None,
    ):
        self.manifest = manifest
        self.rpc_timeout = resolve_rpc_timeout(rpc_timeout)
        self.max_duration = resolve_max_duration(max_duration)
        self.manifest_path = manifest_path
        self.agent_info: Dict[str, Any] = {}

    def run_scenarios(self):
        started_at = audit_module.utc_now()
        run_start = time.perf_counter()
        deadline = run_start + self.max_duration if self.max_duration else None

        report_data: List[Dict[str, Any]] = []
        run_exit_reason = audit_module.STATUS_OK

        for scenario in self.manifest.scenarios:
            if deadline is not None and time.perf_counter() >= deadline:
                run_exit_reason = ECPBudgetExceeded.exit_reason
                logger.error(
                    "Wall-clock budget of %.1fs exhausted. Skipping scenario: %s",
                    self.max_duration,
                    scenario.name,
                )
                report_data.append(
                    self._skipped_scenario(
                        scenario,
                        ECPBudgetExceeded.exit_reason,
                        f"Run exceeded --max-duration of {self.max_duration:.1f}s",
                    )
                )
                continue

            logger.info("Scenario: %s", scenario.name)
            record = self._run_scenario(scenario, deadline)
            report_data.append(record)

            if record["exit_reason"] == ECPBudgetExceeded.exit_reason:
                run_exit_reason = ECPBudgetExceeded.exit_reason
            elif record["status"] != audit_module.STATUS_OK and run_exit_reason == audit_module.STATUS_OK:
                run_exit_reason = record["exit_reason"]

        total_passed, total_checks = _tally_checks(report_data)
        duration_ms = (time.perf_counter() - run_start) * 1000

        logger.info("Run Complete. Passed: %d/%d", total_passed, total_checks)
        if run_exit_reason != audit_module.STATUS_OK:
            logger.error("Run degraded. Exit reason: %s", run_exit_reason)

        audit_payload = audit_module.build_audit(
            report_data,
            target=self.manifest.target,
            manifest_path=self.manifest_path,
            manifest_name=getattr(self.manifest, "name", None),
            agent=self.agent_info,
            rpc_timeout=self.rpc_timeout,
            max_duration=self.max_duration,
            started_at=started_at,
            finished_at=audit_module.utc_now(),
            duration_ms=duration_ms,
            exit_reason=run_exit_reason,
        )

        # Return structured report data
        return {
            "passed": total_passed,
            "total": total_checks,
            "scenarios": report_data,
            "exit_reason": run_exit_reason,
            "audit": audit_payload,
        }

    def _run_scenario(self, scenario, deadline: Optional[float]) -> Dict[str, Any]:
        """Run one scenario against a fresh agent, never raising on agent failure.

        A scenario owns its own agent process, so once a step fails the agent is
        assumed unusable: the remaining steps are recorded as skipped and the
        next scenario starts from a clean process.
        """
        steps: List[Dict[str, Any]] = []
        agent = None
        started = False

        try:
            agent = self._create_agent(self.manifest.target, rpc_timeout=self.rpc_timeout)
            agent.start()
            started = True
            init_resp = self._call_rpc(agent, "agent/initialize", {"config": {}}, scenario.name, None)
            init_result = init_resp["result"]
            try:
                validate_initialize_result(init_result)
            except ValueError as exc:
                raise ECPProtocolError(
                    f"Invalid agent/initialize result at scenario='{scenario.name}': {exc}"
                ) from exc
            if not self.agent_info:
                self.agent_info = {
                    "name": init_result.get("name"),
                    "capabilities": init_result.get("capabilities", {}),
                }
        except ECPExecutionError as exc:
            logger.error("Scenario '%s' could not start: %s", scenario.name, exc)
            if started and agent is not None:
                agent.stop()
            return self._skipped_scenario(scenario, exit_reason_for(exc), str(exc))
        except Exception as exc:  # transport construction / process spawn failures
            logger.error("Scenario '%s' could not start: %s", scenario.name, exc)
            if started and agent is not None:
                agent.stop()
            return self._skipped_scenario(scenario, ECPTransportError.exit_reason, str(exc))

        scenario_exit_reason = audit_module.STATUS_OK
        try:
            for index, step in enumerate(scenario.steps):
                if deadline is not None and time.perf_counter() >= deadline:
                    scenario_exit_reason = ECPBudgetExceeded.exit_reason
                    message = f"Run exceeded --max-duration of {self.max_duration:.1f}s"
                    logger.error("%s. Skipping remaining steps in '%s'.", message, scenario.name)
                    steps.extend(self._skipped_steps(scenario.steps[index:], message))
                    break

                record, failure = self._run_step(agent, scenario, step, index + 1)
                steps.append(record)

                if failure is not None:
                    scenario_exit_reason = failure
                    remaining = scenario.steps[index + 1 :]
                    if remaining:
                        steps.extend(
                            self._skipped_steps(
                                remaining,
                                f"Skipped after step {index + 1} failed ({failure})",
                            )
                        )
                    break
        finally:
            agent.stop()

        return {
            "name": scenario.name,
            "status": audit_module.STATUS_OK
            if scenario_exit_reason == audit_module.STATUS_OK
            else audit_module.STATUS_FAILED,
            "exit_reason": scenario_exit_reason,
            "steps": steps,
        }

    def _run_step(self, agent, scenario, step, step_idx: int):
        """Execute one step. Returns (step_record, failure_exit_reason|None)."""
        step_start = time.perf_counter()
        try:
            rpc_resp = self._call_rpc(agent, "agent/step", {"input": step.input}, scenario.name, step_idx)
            try:
                result_data = validate_step_result(rpc_resp["result"])
            except ValueError as exc:
                raise ECPProtocolError(
                    f"Invalid agent/step result at scenario='{scenario.name}', step={step_idx}: {exc}"
                ) from exc
        except ECPExecutionError as exc:
            duration_ms = (time.perf_counter() - step_start) * 1000
            reason = exit_reason_for(exc)
            logger.error("FAIL | step %d did not complete (%s): %s", step_idx, reason, exc)
            return (
                {
                    "input": step.input,
                    "output": None,
                    "evaluation_context": None,
                    "tool_calls": [],
                    "logs": None,
                    "checks": [_execution_check(f"{reason}: {exc}")],
                    "status": audit_module.STATUS_FAILED,
                    "exit_reason": reason,
                    "duration_ms": duration_ms,
                    "usage": None,
                    "error": str(exc),
                },
                reason,
            )

        duration_ms = (time.perf_counter() - step_start) * 1000

        step_result = StepResult(
            status=result_data.get("status", "done"),
            public_output=result_data.get("public_output"),
            evaluation_context=result_data.get("evaluation_context") or result_data.get("private_thought"),
            private_thought=result_data.get("private_thought") or result_data.get("evaluation_context"),
            logs=result_data.get("logs"),
            tool_calls=result_data.get("tool_calls") if isinstance(result_data.get("tool_calls"), list) else None,
            usage=result_data.get("usage") if isinstance(result_data.get("usage"), dict) else None,
        )

        logger.info("Step %d: Input='%s'", step_idx, step.input)
        logger.info("Output: %s", step_result.public_output)
        logger.debug("Latency: %.1fms", duration_ms)
        if step_result.evaluation_context:
            logger.debug("Evaluation context: %s", step_result.evaluation_context)

        checks = evaluate_step(step, step_result)
        for check in checks:
            status = "PASS" if check["passed"] else "FAIL"
            logger.info("%s | %s on %s", status, check["type"], check["field"])
            if check["type"] == "llm_judge" or not check["passed"]:
                logger.info("Reason: %s", check["reasoning"])

        return (
            {
                "input": step.input,
                "output": step_result.public_output,
                "evaluation_context": step_result.evaluation_context,
                "tool_calls": step_result.tool_calls or [],
                "logs": step_result.logs,
                "checks": checks,
                "status": audit_module.STATUS_OK,
                "exit_reason": audit_module.STATUS_OK,
                "duration_ms": duration_ms,
                "usage": step_result.usage,
                "error": None,
            },
            None,
        )

    def _skipped_scenario(self, scenario, exit_reason: str, message: str) -> Dict[str, Any]:
        return {
            "name": scenario.name,
            "status": audit_module.STATUS_FAILED,
            "exit_reason": exit_reason,
            "steps": self._skipped_steps(scenario.steps, message),
        }

    def _skipped_steps(self, steps, message: str) -> List[Dict[str, Any]]:
        """Skipped steps still record a failed check so CI cannot read them as passing."""
        return [
            {
                "input": step.input,
                "output": None,
                "evaluation_context": None,
                "tool_calls": [],
                "logs": None,
                "checks": [_execution_check(message)],
                "status": audit_module.STATUS_SKIPPED,
                "exit_reason": audit_module.STATUS_SKIPPED,
                "duration_ms": 0.0,
                "usage": None,
                "error": message,
            }
            for step in steps
        ]

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
        where = _where(scenario_name, step_idx)
        try:
            validate_rpc_response(rpc_resp, method)
        except ValueError as exc:
            # A well-formed JSON-RPC error is the agent reporting failure;
            # anything else means the envelope itself broke the contract.
            failure = ECPAgentError if isinstance(rpc_resp, dict) and "error" in rpc_resp else ECPProtocolError
            raise failure(f"RPC call failed ({method}) at {where}: {exc}") from exc

    def _call_rpc(
        self,
        agent: Any,
        method: str,
        params: Dict[str, Any],
        scenario_name: str,
        step_idx: Optional[int],
    ) -> Dict[str, Any]:
        where = _where(scenario_name, step_idx)
        try:
            response = agent.send_rpc(method, params)
        except ECPExecutionError as exc:
            # Preserve the transport's classification, add scenario/step context.
            raise type(exc)(f"RPC call failed ({method}) at {where}: {exc}") from exc
        except Exception as exc:
            raise ECPTransportError(f"RPC call failed ({method}) at {where}: {exc}") from exc
        self._ensure_rpc_success(response, scenario_name, step_idx, method)
        return response


def resolve_rpc_timeout(value: Optional[float] = None) -> float:
    """Resolve and validate an explicit timeout or the ECP_RPC_TIMEOUT fallback."""
    raw_value: Any = value if value is not None else os.environ.get("ECP_RPC_TIMEOUT", "30")
    try:
        timeout = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"RPC timeout must be a positive number; received {raw_value!r}"
        ) from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError(f"RPC timeout must be a positive finite number; received {raw_value!r}")
    return timeout


def resolve_max_duration(value: Optional[float] = None) -> Optional[float]:
    """Resolve the optional wall-clock budget for a whole run.

    The per-RPC timeout cannot bound total runtime: an agent that answers just
    inside the timeout on every step can still pin a CI job for hours. This is
    the run-level ceiling. Returns None when no budget is configured.
    """
    raw_value: Any = value if value is not None else os.environ.get("ECP_MAX_DURATION")
    if raw_value is None or raw_value == "":
        return None
    try:
        duration = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Max duration must be a positive number; received {raw_value!r}"
        ) from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Max duration must be a positive finite number; received {raw_value!r}")
    return duration


def _where(scenario_name: str, step_idx: Optional[int]) -> str:
    where = f"scenario='{scenario_name}'"
    if step_idx is not None:
        where += f", step={step_idx}"
    return where


def _execution_check(message: str) -> Dict[str, Any]:
    """A synthetic failed check standing in for a step that never produced a result.

    Without this the run would report 0/0 checks for a timed-out step, which CI
    reads as a pass.
    """
    return {
        "type": "execution",
        "field": "agent",
        "passed": False,
        "score": 0.0,
        "reasoning": message,
    }


def _tally_checks(scenarios: List[Dict[str, Any]]) -> Tuple[int, int]:
    passed = 0
    total = 0
    for scenario in scenarios:
        for step in scenario.get("steps", []):
            for check in step.get("checks", []):
                total += 1
                if check.get("passed"):
                    passed += 1
    return passed, total


def _is_http_url(target: str) -> bool:
    parsed = urlparse(target)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _ensure_response_id(response: Dict[str, Any], request_id: int) -> None:
    response_id = response.get("id")
    if type(response_id) is not type(request_id) or response_id != request_id:
        raise ECPProtocolError(
            f"JSON-RPC response id mismatch: expected {request_id}, got {response_id}"
        )
