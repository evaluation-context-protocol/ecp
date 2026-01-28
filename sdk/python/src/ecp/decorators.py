import functools
from typing import Callable, Optional, Any, Dict
from dataclasses import dataclass

# --- Public Types ---
@dataclass
class Result:
    """The object the user must return from their step function."""
    status: str = "done"  # 'done', 'paused'
    public_output: Optional[str] = None
    private_thought: Optional[str] = None
    tool_calls: Optional[list] = None
    logs: Optional[str] = None

# --- Global Registry (Where we store the agent hooks) ---
_CURRENT_AGENT_INSTANCE = None
_HOOKS = {
    "step": None,
    "reset": None,
    "inspect": {}
}

# --- Decorators ---
def agent(name: str = "AnonymousAgent"):
    """Class Decorator: Marks a class as an ECP Agent."""
    def wrapper(cls):
        cls._ecp_meta = {"name": name}
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