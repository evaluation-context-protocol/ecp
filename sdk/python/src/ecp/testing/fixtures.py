"""
ecp.testing.fixtures
====================
Capture the *shape* of a framework response object as JSON, and rebuild an
object that behaves like it.

Adapters normalize framework-specific response objects into an ECP ``Result``.
That normalization walks framework internals - CrewAI reads
``tasks_output[].messages[]``, LangChain reads ``LLMResult.generations`` - so it
breaks whenever a framework reshapes those objects, and it breaks *silently*:
tool calls come back empty and every ``tool_usage`` grader fails as if the agent
regressed.

Recording the real object once lets the adapter be replayed against it forever,
with no framework install and no API key. Re-recording against a newer framework
version makes a shape change show up as a fixture diff instead of a mystery.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Values stored verbatim. ``bool`` is a subclass of ``int``; both are fine here.
_PRIMITIVES = (str, int, float, bool, type(None))

#: Attributes adapters read that may be properties rather than instance state,
#: so they never appear in ``__dict__`` and must be probed explicitly.
PROBE_ATTRS: Tuple[str, ...] = (
    "raw",
    "output",
    "content",
    "result",
    "final_output",
    "response",
    "text",
    "metadata",
    "tasks_output",
    "messages",
    "tool_calls",
    "tools",
    "actions",
    "events",
    "tool_usage",
    "data",
    "generations",
    "message",
    "additional_kwargs",
    "new_messages",
    "all_messages",
    "parts",
)

#: Zero-argument accessors whose *return value* the adapters consume, e.g.
#: PydanticAI's ``result.usage()``. Recorded by calling them once.
CALLABLE_ATTRS: Tuple[str, ...] = ("usage", "new_messages", "all_messages")

DEFAULT_MAX_DEPTH = 12


class RecordedObject:
    """Stands in for a framework object, exposing only what was recorded.

    Uses ``__slots__`` plus a ``__dict__`` property so that ``vars(obj)`` and
    ``obj.__dict__`` return the *recorded* attributes. Adapters call
    ``getattr(value, "__dict__")`` when coercing unknown objects to dicts; a
    normal instance dict would leak this class's internals into their output.
    """

    __slots__ = ("_type_name", "_attrs", "_methods", "_has_model_dump", "_has_dict")

    def __init__(
        self,
        type_name: str,
        attrs: Dict[str, Any],
        methods: Optional[Dict[str, Any]] = None,
        has_model_dump: bool = False,
        has_dict: bool = False,
    ) -> None:
        object.__setattr__(self, "_type_name", type_name)
        object.__setattr__(self, "_attrs", attrs)
        object.__setattr__(self, "_methods", methods or {})
        object.__setattr__(self, "_has_model_dump", has_model_dump)
        object.__setattr__(self, "_has_dict", has_dict)

    @property  # type: ignore[override]
    def __dict__(self) -> Dict[str, Any]:  # noqa: D105
        return dict(self._attrs)

    def __getattr__(self, name: str) -> Any:
        methods = object.__getattribute__(self, "_methods")
        if name in methods:
            value = methods[name]
            return lambda: value
        if name == "model_dump" and object.__getattribute__(self, "_has_model_dump"):
            return lambda *_args, **_kwargs: dict(object.__getattribute__(self, "_attrs"))
        if name == "dict" and object.__getattribute__(self, "_has_dict"):
            return lambda *_args, **_kwargs: dict(object.__getattribute__(self, "_attrs"))
        attrs = object.__getattribute__(self, "_attrs")
        if name in attrs:
            return attrs[name]
        raise AttributeError(
            f"{object.__getattribute__(self, '_type_name')!r} fixture has no attribute {name!r}"
        )

    def __repr__(self) -> str:
        return f"<RecordedObject {self._type_name} attrs={sorted(self._attrs)}>"


def record(value: Any, *, max_depth: int = DEFAULT_MAX_DEPTH, _depth: int = 0) -> Any:
    """Serialize a framework object into a JSON-safe structural capture."""
    if isinstance(value, _PRIMITIVES):
        return value

    if _depth >= max_depth:
        return {"__kind__": "truncated", "repr": _safe_repr(value)}

    if isinstance(value, (list, tuple)):
        return [record(item, max_depth=max_depth, _depth=_depth + 1) for item in value]

    if isinstance(value, dict):
        return {
            "__kind__": "dict",
            "items": {
                str(key): record(item, max_depth=max_depth, _depth=_depth + 1)
                for key, item in value.items()
            },
        }

    return _record_object(value, max_depth=max_depth, depth=_depth)


def _record_object(value: Any, *, max_depth: int, depth: int) -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}

    instance_state = getattr(value, "__dict__", None)
    if isinstance(instance_state, dict):
        for key, item in instance_state.items():
            if key.startswith("_") or callable(item):
                continue
            attrs[key] = record(item, max_depth=max_depth, _depth=depth + 1)

    # Properties never show up in __dict__, so probe the names adapters read.
    for name in PROBE_ATTRS:
        if name in attrs:
            continue
        found, item = _safe_getattr(value, name)
        if not found or callable(item):
            continue
        attrs[name] = record(item, max_depth=max_depth, _depth=depth + 1)

    methods: Dict[str, Any] = {}
    for name in CALLABLE_ATTRS:
        found, item = _safe_getattr(value, name)
        if not found or not callable(item):
            continue
        try:
            methods[name] = record(item(), max_depth=max_depth, _depth=depth + 1)
        except Exception:
            # An accessor that needs arguments or fails is simply not recorded.
            continue

    return {
        "__kind__": "object",
        "type": type(value).__name__,
        "attrs": attrs,
        "methods": methods,
        "has_model_dump": callable(getattr(value, "model_dump", None)),
        "has_dict": callable(getattr(value, "dict", None)),
    }


def rebuild(payload: Any) -> Any:
    """Inverse of :func:`record` - produce something adapters can walk."""
    if isinstance(payload, _PRIMITIVES):
        return payload

    if isinstance(payload, list):
        return [rebuild(item) for item in payload]

    if not isinstance(payload, dict):
        return payload

    kind = payload.get("__kind__")

    if kind == "dict":
        return {key: rebuild(item) for key, item in payload.get("items", {}).items()}

    if kind == "truncated":
        return payload.get("repr")

    if kind == "object":
        return RecordedObject(
            type_name=payload.get("type", "Recorded"),
            attrs={key: rebuild(item) for key, item in payload.get("attrs", {}).items()},
            methods={key: rebuild(item) for key, item in payload.get("methods", {}).items()},
            has_model_dump=bool(payload.get("has_model_dump")),
            has_dict=bool(payload.get("has_dict")),
        )

    # A bare mapping with no marker is treated as a plain dict.
    return {key: rebuild(item) for key, item in payload.items()}


def _safe_getattr(value: Any, name: str) -> Tuple[bool, Any]:
    try:
        return True, getattr(value, name)
    except Exception:
        # Properties can raise; a framework object that errors on access is
        # simply treated as not having the attribute.
        return False, None


def _safe_repr(value: Any) -> str:
    try:
        return repr(value)[:200]
    except Exception:
        return f"<unreprable {type(value).__name__}>"


def iter_recorded_types(payload: Any) -> Iterable[str]:
    """Yield every recorded object type name. Useful for asserting fixture shape."""
    if isinstance(payload, list):
        for item in payload:
            yield from iter_recorded_types(item)
        return
    if not isinstance(payload, dict):
        return
    if payload.get("__kind__") == "object":
        yield payload.get("type", "Recorded")
        for item in payload.get("attrs", {}).values():
            yield from iter_recorded_types(item)
        for item in payload.get("methods", {}).values():
            yield from iter_recorded_types(item)
    elif payload.get("__kind__") == "dict":
        for item in payload.get("items", {}).values():
            yield from iter_recorded_types(item)


__all__: List[str] = [
    "CALLABLE_ATTRS",
    "PROBE_ATTRS",
    "RecordedObject",
    "iter_recorded_types",
    "rebuild",
    "record",
]
