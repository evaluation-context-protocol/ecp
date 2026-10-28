"""
Drive one ECP agent from Python, for evaluators that are not the ECP runner.

ECP sits between agents and evaluation tools. The runner is one evaluator; DeepEval,
Promptfoo or a team's own harness are others. They all need the same thing: start an
agent, initialize it, send it input, and get back what it said *and* what it did. This
module is that, with the runner's validation, and nothing about grading.

    from ecp_runtime.session import ECPSession

    with ECPSession("python agent.py") as agent:
        result = agent.step("Can I get a refund for order A100?")
        result.public_output   # what the agent said
        result.tool_calls      # what it did: [{"name": ..., "arguments": {...}}, ...]

The target is the same string a manifest's `target:` takes: a shell command for a
stdio agent, or an http(s) URL for a Streamable HTTP one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .conformance import (
    validate_initialize_result,
    validate_rpc_response,
    validate_step_result,
)
from .errors import ECPAgentError, ECPProtocolError
from .protocol import initialize_params, negotiate_protocol_version
from .runner import AgentProcess, HTTPAgentClient, _is_http_url, resolve_rpc_timeout


@dataclass
class StepOutput:
    """One agent/step result, normalised the way the runner normalises it."""

    input: str
    status: str
    public_output: Optional[str]
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    evaluation_context: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    logs: Optional[str] = None
    #: Whether the agent declared it reports tool calls. When False, an empty
    #: `tool_calls` means "not reported", not "none were made".
    tool_calls_declared: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input": self.input,
            "status": self.status,
            "public_output": self.public_output,
            "tool_calls": self.tool_calls,
            "evaluation_context": self.evaluation_context,
            "usage": self.usage,
            "tool_calls_declared": self.tool_calls_declared,
        }


class ECPSession:
    """A started, initialized ECP agent. Use as a context manager, or call close()."""

    def __init__(self, target: str, *, timeout: Optional[float] = None, config: Optional[dict] = None):
        self.target = target
        self.timeout = resolve_rpc_timeout(timeout)
        self.config = config
        self.agent_info: Dict[str, Any] = {}
        self._client = None

    # -- lifecycle -----------------------------------------------------------

    def __enter__(self) -> "ECPSession":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> "ECPSession":
        client = HTTPAgentClient if _is_http_url(self.target) else AgentProcess
        self._client = client(self.target, rpc_timeout=self.timeout)
        self._client.start()
        try:
            result = self._call("agent/initialize", initialize_params(self.config))
            try:
                validate_initialize_result(result)
            except ValueError as exc:
                raise ECPProtocolError(f"invalid agent/initialize result: {exc}") from exc
            negotiation = negotiate_protocol_version(result.get("protocol_version"))
            self.agent_info = {
                "name": result.get("name"),
                "protocol_version": negotiation.version,
                "capabilities": result.get("capabilities") or {},
            }
        except Exception:
            self.close()
            raise
        return self

    def close(self) -> None:
        if self._client is not None:
            self._client.stop()
            self._client = None

    # -- protocol ------------------------------------------------------------

    @property
    def capabilities(self) -> Dict[str, Any]:
        return self.agent_info.get("capabilities") or {}

    def step(self, text: str) -> StepOutput:
        result = self._call("agent/step", {"input": text})
        try:
            data = validate_step_result(result)
        except ValueError as exc:
            raise ECPProtocolError(f"invalid agent/step result: {exc}") from exc
        calls = data.get("tool_calls") if isinstance(data.get("tool_calls"), list) else []
        return StepOutput(
            input=text,
            status=data.get("status", "done"),
            public_output=data.get("public_output"),
            tool_calls=calls,
            evaluation_context=data.get("evaluation_context") or data.get("private_thought"),
            usage=data.get("usage") if isinstance(data.get("usage"), dict) else None,
            logs=data.get("logs"),
            tool_calls_declared="tool_calls" in self.capabilities,
        )

    def reset(self) -> None:
        self._call("agent/reset", {})

    def _call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._client is None:
            raise ECPProtocolError("session is not open")
        response = self._client.send_rpc(method, params)
        try:
            validate_rpc_response(response, method)
        except ValueError as exc:
            failure = ECPAgentError if isinstance(response, dict) and "error" in response else ECPProtocolError
            raise failure(f"{method} failed: {exc}") from exc
        return response["result"]


def run_steps(target: str, inputs: List[str], *, timeout: Optional[float] = None) -> List[StepOutput]:
    """Run inputs through one fresh agent, in order, and return every step's output."""
    with ECPSession(target, timeout=timeout) as session:
        return [session.step(text) for text in inputs]
