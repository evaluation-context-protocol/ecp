from dataclasses import dataclass
from typing import Any, Dict, Optional

USAGE_FIELDS = ("input_tokens", "output_tokens", "total_tokens")


# --- Public Types ---
@dataclass
class Result:
    """The object the user must return from their step function."""
    status: str = "done"  # 'done', 'paused'
    public_output: Optional[str] = None
    evaluation_context: Optional[str] = None
    # Deprecated compatibility alias. Prefer evaluation_context for new agents.
    private_thought: Optional[str] = None
    tool_calls: Optional[list] = None
    logs: Optional[str] = None
    # Optional token accounting, surfaced in the runtime's audit payload.
    usage: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.status not in {"done", "paused"}:
            raise ValueError("status must be 'done' or 'paused'")
        for field_name in ("public_output", "evaluation_context", "private_thought", "logs"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{field_name} must be a string or None")
        if self.tool_calls is not None:
            if not isinstance(self.tool_calls, list):
                raise TypeError("tool_calls must be a list or None")
            for index, tool_call in enumerate(self.tool_calls):
                if not isinstance(tool_call, dict):
                    raise TypeError(f"tool_calls[{index}] must be a dictionary")
                if not isinstance(tool_call.get("name"), str) or not tool_call["name"]:
                    raise ValueError(f"tool_calls[{index}].name must be a non-empty string")
                if "arguments" in tool_call and not isinstance(tool_call["arguments"], dict):
                    raise TypeError(f"tool_calls[{index}].arguments must be a dictionary")
        if self.usage is not None:
            if not isinstance(self.usage, dict):
                raise TypeError("usage must be a dictionary or None")
            for field_name in USAGE_FIELDS:
                value = self.usage.get(field_name)
                if value is None:
                    continue
                if isinstance(value, bool) or not isinstance(value, int):
                    raise TypeError(f"usage.{field_name} must be an integer or None")
                if value < 0:
                    raise ValueError(f"usage.{field_name} must not be negative")
        if self.evaluation_context is None and self.private_thought is not None:
            self.evaluation_context = self.private_thought
        elif self.private_thought is None and self.evaluation_context is not None:
            self.private_thought = self.evaluation_context

# --- Global Registry (Where we store the agent hooks) ---
_CURRENT_AGENT_INSTANCE = None
_HOOKS = {
    "step": None,
    "reset": None,
    "inspect": {}
}

# --- Decorators ---
#: Capabilities an agent may declare. Presence means supported; the value is an
#: options object, empty when there are no options.
#:
#: Only `reset` can be inferred honestly - the SDK knows whether an @on_reset
#: hook exists. The rest depend on what a step actually returns at runtime, so
#: the agent author declares them.
KNOWN_CAPABILITIES = (
    "tool_calls",
    "evaluation_context",
    "usage",
    "reset",
    "multi_turn",
)


def agent(name: str = "AnonymousAgent", capabilities: Optional[Dict[str, Any]] = None):
    """Class Decorator: Marks a class as an ECP Agent.

    ``capabilities`` tells the runtime what this agent can report, so a manifest
    asking for something the agent never produces fails with a clear message
    instead of N identical grader failures. Declaring nothing keeps the previous
    permissive behaviour.
    """
    declared = dict(capabilities or {})
    for key, value in declared.items():
        if not isinstance(key, str) or not key:
            raise ValueError("capability names must be non-empty strings")
        if not isinstance(value, dict):
            raise TypeError(
                f"capability {key!r} must map to an options object (use {{}} when there are none)"
            )

    def wrapper(cls):
        cls._ecp_meta = {"name": name, "capabilities": declared}
        return cls
    return wrapper

def on_step(func):
    """Method Decorator: Registers the function to handle 'agent/step'."""
    _HOOKS["step"] = func.__name__
    return func

def on_reset(func):
    """Method Decorator: Registers the function to handle 'agent/reset'."""
    _HOOKS["reset"] = func.__name__
    return func

def expose_state(path: str):
    """Method Decorator: Allows runtime to inspect this getter."""
    def decorator(func):
        _HOOKS["inspect"][path] = func.__name__
        return func
    return decorator
