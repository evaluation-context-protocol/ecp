"""
A Promptfoo provider that talks to any ECP agent.

Promptfoo sends a prompt; this starts the agent named by `target`, runs one
agent/step, and returns the reply as Promptfoo's `output`. Everything else the agent
reported goes in `metadata`, so assertions can check what the agent *did*:

    providers:
      - id: file://integrations/promptfoo/ecp_provider.py
        config:
          target: python my_agent.py       # same string as a manifest's target:
          rpc_timeout: 120                 # seconds per ECP call (optional)
          timeout: 300000                  # Promptfoo's own worker limit, in ms; an
                                           # LLM agent needs more than its default

    assert:
      - type: llm-rubric                    # grade the reply as usual
        value: Does not claim a refund was issued
      - type: javascript                    # grade the action
        value: "!context.providerResponse.metadata.tool_names.includes('issue_refund')"

`metadata` carries `tool_calls`, `tool_names`, `evaluation_context`, `usage`, the
agent's declared `capabilities`, and `tool_calls_declared`. When that last one is
false the agent never promised to report tool calls, so an empty list proves nothing;
check it before trusting a "never called X" assertion.

Each call starts a fresh agent, so tests cannot leak state into each other.
"""

from typing import Any, Dict, Optional

from ..session import ECPSession


def call_api(prompt: str, options: Optional[Dict[str, Any]] = None, context: Optional[Dict[str, Any]] = None):
    config = (options or {}).get("config") or {}
    target = config.get("target")
    if not target:
        return {"error": "ECP provider needs config.target (the agent command or URL)"}
    try:
        with ECPSession(target, timeout=config.get("rpc_timeout")) as session:
            step = session.step(prompt)
            info = dict(session.agent_info)
    except Exception as exc:  # noqa: BLE001 - Promptfoo reports provider errors as data
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "output": step.public_output or "",
        "metadata": {
            "agent": info.get("name"),
            "capabilities": info.get("capabilities") or {},
            "tool_calls": step.tool_calls,
            "tool_names": [c.get("name") for c in step.tool_calls],
            "tool_calls_declared": step.tool_calls_declared,
            "evaluation_context": step.evaluation_context,
            "usage": step.usage,
            "status": step.status,
        },
    }
