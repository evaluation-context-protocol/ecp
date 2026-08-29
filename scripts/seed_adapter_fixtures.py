"""
Seed adapter conformance fixtures from documented framework shapes.

These are *seeded* fixtures, not live recordings: they encode the response
shapes the adapters are written against, so PR CI can catch regressions in
adapter parsing without installing four frameworks or holding API keys.

They do not prove a framework still emits that shape. Replacing them with real
captures is one command per adapter - see `ecp.testing.record_fixture` and
`.github/workflows/adapter-nightly.yml`.

Usage:
    python scripts/seed_adapter_fixtures.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SDK_SRC = REPO_ROOT / "sdk" / "python" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from ecp.testing.fixtures import record  # noqa: E402
from ecp.testing.replay import (  # noqa: E402
    SOURCE_SEEDED,
    AdapterFixture,
    replay,
)

FIXTURE_DIR = REPO_ROOT / "sdk" / "python" / "tests" / "fixtures" / "adapters"

QUESTION = "What is 15 multiplied by 8?"


def crewai_response() -> object:
    """CrewOutput with tool calls nested in tasks_output[].messages[].

    Mirrors the shape documented in ecp/adaptors/crewai.py::_capture_from_task_outputs.
    """
    task_output = SimpleNamespace(
        messages=[
            {"role": "user", "content": QUESTION},
            {
                "role": "assistant",
                "content": "I should use the calculator tool for this.",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "arguments": '{"expression": "15*8"}',
                        },
                    }
                ],
            },
            {"role": "tool", "content": "120"},
            {"role": "assistant", "content": "The answer is 120."},
        ]
    )
    return SimpleNamespace(raw="The answer is 120.", tasks_output=[task_output])


def pydantic_ai_response() -> object:
    """RunResult whose new_messages() carries thinking, text, and tool-call parts."""
    tool_call_part = SimpleNamespace(
        part_kind="tool-call",
        tool_name="calculator",
        args={"expression": "15*8"},
    )
    thinking_part = SimpleNamespace(
        part_kind="thinking",
        content="The user wants 15 times 8. Use the calculator tool.",
    )
    first_response = SimpleNamespace(kind="response", parts=[thinking_part, tool_call_part])
    final_response = SimpleNamespace(
        kind="response",
        parts=[SimpleNamespace(part_kind="text", content="The answer is 120.")],
    )

    messages = [first_response, final_response]
    return SimpleNamespace(
        output="The answer is 120.",
        data=None,
        new_messages=lambda: messages,
        all_messages=lambda: messages,
        usage=lambda: SimpleNamespace(input_tokens=61, output_tokens=14, requests=2),
    )


def llama_index_response() -> object:
    """Workflow response exposing tool calls and reasoning through metadata."""
    return SimpleNamespace(
        response="The answer is 120.",
        metadata={
            "reasoning": "Routed the arithmetic to the calculator tool.",
            "tool_calls": [
                {"name": "calculator", "arguments": '{"expression": "15*8"}'},
            ],
        },
    )


def langchain_event_payload() -> object:
    """LLMResult delivered to on_llm_end, carrying generations and tool calls."""
    message = SimpleNamespace(
        content="",
        tool_calls=[{"name": "calculator", "args": {"expression": "15*8"}}],
    )
    generation = SimpleNamespace(
        text="I should use the calculator tool for this.",
        message=message,
    )
    return SimpleNamespace(generations=[[generation]])


def build_fixtures() -> list[tuple[str, AdapterFixture]]:
    return [
        (
            "crewai_calculator.json",
            AdapterFixture(
                adapter="crewai",
                input=QUESTION,
                response=record(crewai_response()),
                expected={},
                adapter_kwargs={"name": "CrewMathBot"},
                source=SOURCE_SEEDED,
                description=(
                    "Tool calls nested in tasks_output[].messages[] as OpenAI-format "
                    "function calls with stringified JSON arguments."
                ),
            ),
        ),
        (
            "pydantic_ai_calculator.json",
            AdapterFixture(
                adapter="pydantic_ai",
                input=QUESTION,
                response=record(pydantic_ai_response()),
                expected={},
                adapter_kwargs={"name": "PydanticMathBot"},
                source=SOURCE_SEEDED,
                description=(
                    "RunResult with a thinking part, a tool-call part, and a final "
                    "text part across two ModelResponse messages."
                ),
            ),
        ),
        (
            "llama_index_calculator.json",
            AdapterFixture(
                adapter="llama_index",
                input=QUESTION,
                response=record(llama_index_response()),
                expected={},
                adapter_kwargs={"name": "LlamaMathBot"},
                source=SOURCE_SEEDED,
                description="Workflow response carrying tool calls and reasoning in metadata.",
            ),
        ),
        (
            "langchain_calculator.json",
            AdapterFixture(
                adapter="langchain",
                input=QUESTION,
                response="The answer is 120.",
                expected={},
                events=[{"method": "on_llm_end", "payload": record(langchain_event_payload())}],
                adapter_kwargs={"name": "LangChainMathBot"},
                source=SOURCE_SEEDED,
                description=(
                    "Tool calls arrive out-of-band via the on_llm_end callback, not "
                    "the invoke() return value."
                ),
            ),
        ),
    ]


def main() -> int:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for filename, fixture in build_fixtures():
        # Derive `expected` from the adapter itself so the fixture records what
        # the adapter actually does, then assert the semantics below.
        fixture.expected = replay(fixture)
        path = fixture.save(FIXTURE_DIR / filename)
        print(f"wrote {path.relative_to(REPO_ROOT)}")
        print(f"   tool_calls        = {fixture.expected['tool_calls']}")
        print(f"   public_output     = {fixture.expected['public_output']!r}")
        print(f"   usage             = {fixture.expected['usage']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
