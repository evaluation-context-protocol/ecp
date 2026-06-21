import os
import pytest
from typing import Any, Dict

from .runner import _create_agent

def pytest_addoption(parser):
    parser.addoption(
        "--ecp-target",
        action="store",
        default=None,
        help="The target command or HTTP URL for the ECP agent"
    )

class ECPAgentFixture:
    def __init__(self, target: str, rpc_timeout: float = 30.0):
        self.target = target
        self.rpc_timeout = rpc_timeout
        self._agent = None
    
    def start(self):
        self._agent = _create_agent(self.target, self.rpc_timeout)
        self._agent.start()
        resp = self._agent.send_rpc("agent/initialize", {"config": {}})
        self._ensure_rpc_success(resp, "agent/initialize")
        return self

    def stop(self):
        if self._agent:
            self._agent.stop()
            self._agent = None

    def step(self, input_text: str) -> Dict[str, Any]:
        resp = self._agent.send_rpc("agent/step", {"input": input_text})
        self._ensure_rpc_success(resp, "agent/step")
        return resp.get("result", {})

    def reset(self) -> Dict[str, Any]:
        resp = self._agent.send_rpc("agent/reset", {})
        self._ensure_rpc_success(resp, "agent/reset")
        return resp.get("result", {})

    def _ensure_rpc_success(self, rpc_resp: Dict[str, Any], method: str) -> None:
        if "error" not in rpc_resp:
            return
        error = rpc_resp.get("error") or {}
        code = error.get("code")
        message = error.get("message", "Unknown JSON-RPC error")
        raise RuntimeError(
            f"RPC call failed ({method}): code={code}, message={message}"
        )

@pytest.fixture
def ecp_agent(request):
    target = request.config.getoption("--ecp-target")
    marker = request.node.get_closest_marker("ecp")
    if marker and "target" in marker.kwargs:
        target = marker.kwargs["target"]
        
    if not target:
        pytest.skip("No ECP target specified. Use --ecp-target or @pytest.mark.ecp(target=...)")
        
    rpc_timeout = float(os.environ.get("ECP_RPC_TIMEOUT", "30"))
    agent = ECPAgentFixture(target, rpc_timeout=rpc_timeout)
    agent.start()
    
    yield agent
    
    agent.stop()

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "ecp: marks tests that require an ECP agent"
    )
