"""
Adapter conformance: replay every recorded framework exchange.

Adapters walk framework internals (CrewAI's ``tasks_output[].messages[]``,
LangChain's ``on_llm_end`` callback) to build an ECP ``Result``. Before this
suite the only adapter tests fed hand-written payloads to normalization helpers,
so a broken traversal shipped green - and surfaced to users as empty
``tool_calls``, which reads as an agent regression rather than an adapter bug.

Each fixture replays without installing the framework or holding an API key.
Regenerate them with ``python scripts/seed_adapter_fixtures.py``; capture real
ones with ``ecp.testing.record_fixture``.
"""

import json
import sys
import unittest
from pathlib import Path

SDK_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from ecp.testing.replay import (
    DRIVERS,
    AdapterFixture,
    diff_expected,
    replay,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "adapters"

REQUIRED_RESULT_KEYS = {"status", "public_output", "evaluation_context", "tool_calls", "usage"}


def _fixture_paths():
    return sorted(FIXTURE_DIR.glob("*.json"))


class FixtureInventoryTests(unittest.TestCase):
    def test_fixtures_exist(self) -> None:
        self.assertTrue(_fixture_paths(), f"No adapter fixtures found in {FIXTURE_DIR}")

    def test_every_adapter_has_at_least_one_fixture(self) -> None:
        """A new adapter without a fixture is an adapter nothing tests."""
        covered = {AdapterFixture.load(path).adapter for path in _fixture_paths()}
        missing = set(DRIVERS) - covered
        self.assertEqual(missing, set(), f"Adapters with no conformance fixture: {sorted(missing)}")

    def test_fixtures_are_well_formed(self) -> None:
        for path in _fixture_paths():
            with self.subTest(fixture=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                for key in ("adapter", "input", "response", "expected"):
                    self.assertIn(key, payload, f"{path.name} missing {key!r}")
                self.assertIn(
                    payload["adapter"],
                    DRIVERS,
                    f"{path.name} targets unknown adapter {payload['adapter']!r}",
                )
                self.assertEqual(
                    set(payload["expected"]),
                    REQUIRED_RESULT_KEYS,
                    f"{path.name} expected block must pin the full Result surface",
                )


class AdapterReplayTests(unittest.TestCase):
    def test_replay_matches_recorded_result(self) -> None:
        """The regression gate: adapter output must not drift from the recording."""
        for path in _fixture_paths():
            with self.subTest(fixture=path.name):
                fixture = AdapterFixture.load(path)
                problems = diff_expected(fixture)
                self.assertEqual(
                    problems,
                    [],
                    f"{path.name} drifted:\n  " + "\n  ".join(problems),
                )

    def test_replay_output_satisfies_the_ecp_contract(self) -> None:
        """Stable-but-wrong output is still wrong, so check the protocol shape."""
        try:
            from ecp_runtime.conformance import validate_step_result
        except ImportError:
            self.skipTest("ecp-runtime not installed; protocol validation skipped")

        for path in _fixture_paths():
            with self.subTest(fixture=path.name):
                actual = replay(AdapterFixture.load(path))
                # The runtime rejects unknown-shaped results; adapters must pass it.
                validate_step_result({k: v for k, v in actual.items() if v is not None})

    def test_every_adapter_captures_the_tool_call(self) -> None:
        """The whole point of ECP over text-only evals is asserting tool use.

        Every fixture is the same calculator scenario across four frameworks, so
        all four must resolve to the identical normalized tool call. This is what
        makes a manifest portable between frameworks.
        """
        for path in _fixture_paths():
            with self.subTest(fixture=path.name):
                actual = replay(AdapterFixture.load(path))
                self.assertEqual(actual["status"], "done")
                self.assertIn("120", actual["public_output"] or "")
                self.assertEqual(
                    actual["tool_calls"],
                    [{"name": "calculator", "arguments": {"expression": "15*8"}}],
                    "stringified JSON arguments must normalize to a dict",
                )


class SeededFixtureProvenanceTests(unittest.TestCase):
    def test_seeded_fixtures_are_labelled(self) -> None:
        """Seeded fixtures prove parsing is stable, not that the shape is current.

        Labelling them keeps that distinction visible, so nobody mistakes a green
        replay suite for evidence that a framework has not changed.
        """
        for path in _fixture_paths():
            with self.subTest(fixture=path.name):
                fixture = AdapterFixture.load(path)
                self.assertIn(fixture.source, {"seeded", "recorded"})
                if fixture.source == "recorded":
                    self.assertIsNotNone(
                        fixture.framework_version,
                        f"{path.name} is a real recording but records no framework version",
                    )


if __name__ == "__main__":
    unittest.main()
