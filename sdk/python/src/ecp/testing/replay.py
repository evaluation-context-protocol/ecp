"""
ecp.testing.replay
==================
Drive an adapter against a recorded framework response and compare the
normalized ``Result`` to what was recorded.

Each adapter is invoked differently, so each needs a driver:

===========  ===================================================================
crewai       ``crew.kickoff(**inputs)`` returns the response.
pydantic_ai  ``agent.run_sync(text)`` returns the result.
llama_index  ``await workflow.run(**inputs)`` returns the response.
langchain    ``runnable.invoke(text, config={"callbacks": [adapter]})`` returns
             the final output, but tool calls arrive out-of-band through the
             ``on_llm_end`` callback, so those are replayed as ``events``.
===========  ===================================================================

Replay is deterministic: the recorded response is fixed, so the adapter's output
is fully determined and can be asserted exactly.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from unittest import mock

from .fixtures import rebuild, record

FIXTURE_VERSION = "1"

#: Fixtures authored from documented framework shapes rather than captured from
#: a live run. Honest about provenance: these prove the adapter's parsing is
#: stable, but only a real recording proves the shape is still current.
SOURCE_SEEDED = "seeded"
SOURCE_RECORDED = "recorded"


@dataclass
class AdapterFixture:
    """One recorded framework interaction and the Result it should normalize to."""

    adapter: str
    input: str
    response: Any
    expected: Dict[str, Any]
    events: List[Dict[str, Any]] = field(default_factory=list)
    adapter_kwargs: Dict[str, Any] = field(default_factory=dict)
    framework_version: Optional[str] = None
    recorded_at: Optional[str] = None
    source: str = SOURCE_SEEDED
    fixture_version: str = FIXTURE_VERSION
    description: Optional[str] = None

    @classmethod
    def load(cls, path: Path) -> "AdapterFixture":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f for f in cls.__dataclass_fields__}  # noqa: SLF001
        return cls(**{key: value for key, value in payload.items() if key in known})

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        return path


def result_to_dict(result: Any) -> Dict[str, Any]:
    """Normalize a ``Result`` into the comparable subset a fixture asserts."""
    return {
        "status": result.status,
        "public_output": result.public_output,
        "evaluation_context": result.evaluation_context,
        "tool_calls": result.tool_calls,
        "usage": getattr(result, "usage", None),
    }


# --- Drivers ---------------------------------------------------------------


def _drive_crewai(fixture: AdapterFixture, response: Any) -> Any:
    from ecp.adaptors.crewai import ECPCrewAIAdapter

    crew = types.SimpleNamespace(kickoff=lambda **_kwargs: response)
    adapter = ECPCrewAIAdapter(crew, **fixture.adapter_kwargs)
    return adapter.step(fixture.input)


def _drive_pydantic_ai(fixture: AdapterFixture, response: Any) -> Any:
    from ecp.adaptors.pydantic_ai import ECPPydanticAIAdapter

    pydantic_agent = types.SimpleNamespace(run_sync=lambda _text, **_kwargs: response)
    adapter = ECPPydanticAIAdapter(pydantic_agent, **fixture.adapter_kwargs)
    return adapter.step(fixture.input)


def _drive_llama_index(fixture: AdapterFixture, response: Any) -> Any:
    from ecp.adaptors.llama_index import ECPLlamaIndexAdapter

    async def _run(**_kwargs: Any) -> Any:
        return response

    workflow = types.SimpleNamespace(run=_run)
    adapter = ECPLlamaIndexAdapter(workflow, **fixture.adapter_kwargs)
    return adapter.step(fixture.input)


def _drive_langchain(fixture: AdapterFixture, response: Any) -> Any:
    adapter_cls = _load_langchain_adapter()

    def _invoke(_text: Any, config: Optional[Dict[str, Any]] = None) -> Any:
        # LangChain surfaces generations and tool calls through callbacks, not
        # the return value, so replay them exactly as the framework would.
        handlers = (config or {}).get("callbacks") or []
        for event in fixture.events:
            payload = rebuild(event.get("payload"))
            for handler in handlers:
                method = getattr(handler, event["method"], None)
                if method is not None:
                    method(payload)
        return response

    runnable = types.SimpleNamespace(invoke=_invoke)
    adapter = adapter_cls(runnable, **fixture.adapter_kwargs)
    return adapter.step(fixture.input)


def _load_langchain_adapter() -> Any:
    """Import the LangChain adapter, stubbing langchain_core when absent.

    The adapter subclasses ``BaseCallbackHandler`` at import time. Stubbing lets
    replay run in PR CI without installing LangChain, while the nightly job
    exercises the real thing.
    """
    try:
        importlib.import_module("langchain_core.callbacks")
    except ImportError:
        callbacks_mod = types.ModuleType("langchain_core.callbacks")
        outputs_mod = types.ModuleType("langchain_core.outputs")
        callbacks_mod.BaseCallbackHandler = object
        outputs_mod.LLMResult = object
        with mock.patch.dict(
            sys.modules,
            {
                "langchain_core": types.ModuleType("langchain_core"),
                "langchain_core.callbacks": callbacks_mod,
                "langchain_core.outputs": outputs_mod,
            },
        ):
            module = importlib.reload(importlib.import_module("ecp.adaptors.langchain"))
        return module.ECPLangChainAdapter

    module = importlib.import_module("ecp.adaptors.langchain")
    return module.ECPLangChainAdapter


DRIVERS: Dict[str, Callable[[AdapterFixture, Any], Any]] = {
    "crewai": _drive_crewai,
    "langchain": _drive_langchain,
    "llama_index": _drive_llama_index,
    "pydantic_ai": _drive_pydantic_ai,
}

#: How each adapter reaches its framework, used when recording a live run.
CALL_SITES: Dict[str, str] = {
    "crewai": "kickoff",
    "langchain": "invoke",
    "llama_index": "run",
    "pydantic_ai": "run_sync",
}


def replay(fixture: AdapterFixture) -> Dict[str, Any]:
    """Run the adapter against the recorded response, returning its Result dict."""
    driver = DRIVERS.get(fixture.adapter)
    if driver is None:
        raise ValueError(
            f"No replay driver for adapter {fixture.adapter!r}. "
            f"Known adapters: {', '.join(sorted(DRIVERS))}"
        )
    response = rebuild(fixture.response)
    return result_to_dict(driver(fixture, response))


def diff_expected(fixture: AdapterFixture) -> List[str]:
    """Return human-readable mismatches between replayed and expected Result."""
    actual = replay(fixture)
    problems: List[str] = []
    for key, expected_value in fixture.expected.items():
        actual_value = actual.get(key)
        if actual_value != expected_value:
            problems.append(f"{key}: expected {expected_value!r}, got {actual_value!r}")
    return problems


# --- Recording -------------------------------------------------------------


def record_fixture(
    adapter: str,
    client: Any,
    input_text: str,
    *,
    adapter_kwargs: Optional[Dict[str, Any]] = None,
    framework_version: Optional[str] = None,
    description: Optional[str] = None,
) -> AdapterFixture:
    """Run an adapter against a *real* framework client and capture the exchange.

    ``client`` is the live framework object the adapter wraps - a CrewAI ``Crew``,
    a PydanticAI ``Agent``, a LangChain runnable, a LlamaIndex workflow. The call
    it makes is intercepted, the response recorded, and the resulting ``Result``
    stored as the expectation.

    Requires the framework installed and, usually, API credentials - so this runs
    in the nightly job or by hand, never in PR CI.
    """
    if adapter not in DRIVERS:
        raise ValueError(f"Unknown adapter {adapter!r}. Known: {', '.join(sorted(DRIVERS))}")

    call_attr = CALL_SITES[adapter]
    captured: Dict[str, Any] = {}
    events: List[Dict[str, Any]] = []
    original = getattr(client, call_attr)

    async def _tee_async(*args: Any, **kwargs: Any) -> Any:
        response = await original(*args, **kwargs)
        captured["response"] = response
        return response

    def _tee(*args: Any, **kwargs: Any) -> Any:
        response = original(*args, **kwargs)
        captured["response"] = response
        return response

    live_adapter = _build_live_adapter(adapter, client, adapter_kwargs or {})

    # LangChain pushes generations and tool calls through the callback handler
    # rather than the return value, and the adapter *is* the handler - so tee
    # its own hook to capture what the framework sent.
    if adapter == "langchain":
        _tee_callback(live_adapter, "on_llm_end", events)

    setattr(client, call_attr, _tee_async if asyncio.iscoroutinefunction(original) else _tee)
    try:
        result = live_adapter.step(input_text)
    finally:
        setattr(client, call_attr, original)

    if "response" not in captured:
        raise RuntimeError(f"Adapter {adapter!r} never called {call_attr!r}; nothing recorded")

    return AdapterFixture(
        adapter=adapter,
        input=input_text,
        response=record(captured["response"]),
        expected=result_to_dict(result),
        events=events,
        adapter_kwargs=adapter_kwargs or {},
        framework_version=framework_version,
        recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        source=SOURCE_RECORDED,
        description=description,
    )


def _build_live_adapter(adapter: str, client: Any, adapter_kwargs: Dict[str, Any]) -> Any:
    if adapter == "crewai":
        from ecp.adaptors.crewai import ECPCrewAIAdapter

        return ECPCrewAIAdapter(client, **adapter_kwargs)
    if adapter == "pydantic_ai":
        from ecp.adaptors.pydantic_ai import ECPPydanticAIAdapter

        return ECPPydanticAIAdapter(client, **adapter_kwargs)
    if adapter == "llama_index":
        from ecp.adaptors.llama_index import ECPLlamaIndexAdapter

        return ECPLlamaIndexAdapter(client, **adapter_kwargs)
    if adapter == "langchain":
        return _load_langchain_adapter()(client, **adapter_kwargs)
    raise ValueError(f"Unknown adapter {adapter!r}")


def _tee_callback(adapter_instance: Any, method_name: str, events: List[Dict[str, Any]]) -> None:
    """Wrap a callback hook so each payload the framework delivers is recorded."""
    original = getattr(adapter_instance, method_name)

    def _wrapped(payload: Any, *args: Any, **kwargs: Any) -> Any:
        events.append({"method": method_name, "payload": record(payload)})
        return original(payload, *args, **kwargs)

    setattr(adapter_instance, method_name, _wrapped)


__all__ = [
    "AdapterFixture",
    "CALL_SITES",
    "DRIVERS",
    "FIXTURE_VERSION",
    "SOURCE_RECORDED",
    "SOURCE_SEEDED",
    "diff_expected",
    "record_fixture",
    "replay",
    "result_to_dict",
]
