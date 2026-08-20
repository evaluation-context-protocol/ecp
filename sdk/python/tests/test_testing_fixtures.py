"""
Tests for the record/rebuild machinery itself.

If the recorder loses fidelity, the conformance suite passes against objects
that do not resemble what frameworks actually emit - a green suite proving
nothing. These tests pin the behaviours the adapters depend on.
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SDK_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from ecp.testing.fixtures import RecordedObject, iter_recorded_types, rebuild, record


class RecordRoundTripTests(unittest.TestCase):
    def test_primitives_and_containers_survive(self) -> None:
        value = {"a": 1, "b": [1, "two", None, True], "c": {"nested": 3.5}}
        self.assertEqual(rebuild(record(value)), value)

    def test_object_attributes_are_reachable(self) -> None:
        original = SimpleNamespace(raw="answer", tasks_output=[SimpleNamespace(messages=[{"role": "user"}])])

        rebuilt = rebuild(record(original))

        self.assertEqual(rebuilt.raw, "answer")
        self.assertEqual(rebuilt.tasks_output[0].messages[0]["role"], "user")

    def test_missing_attributes_raise_attribute_error(self) -> None:
        rebuilt = rebuild(record(SimpleNamespace(raw="x")))

        self.assertFalse(hasattr(rebuilt, "tool_calls"))
        with self.assertRaises(AttributeError):
            _ = rebuilt.tool_calls

    def test_dunder_dict_exposes_recorded_attrs_not_internals(self) -> None:
        """Adapters coerce unknown objects via ``__dict__``.

        A normal instance dict would leak RecordedObject's own state into the
        adapter's metadata payload, silently corrupting extraction.
        """
        rebuilt = rebuild(record(SimpleNamespace(raw="x", tool_calls=[])))

        self.assertEqual(set(rebuilt.__dict__), {"raw", "tool_calls"})
        self.assertEqual(vars(rebuilt), {"raw": "x", "tool_calls": []})
        for key in rebuilt.__dict__:
            self.assertFalse(key.startswith("_"))

    def test_model_dump_presence_is_preserved(self) -> None:
        """Adapters branch on hasattr(value, "model_dump"); fidelity matters."""

        class Pydanticish:
            def __init__(self):
                self.name = "calculator"

            def model_dump(self):
                return {"name": self.name}

        rebuilt = rebuild(record(Pydanticish()))
        self.assertTrue(hasattr(rebuilt, "model_dump"))
        self.assertEqual(rebuilt.model_dump(), {"name": "calculator"})

        plain = rebuild(record(SimpleNamespace(name="calculator")))
        self.assertFalse(hasattr(plain, "model_dump"))

    def test_zero_arg_accessors_are_recorded_as_callables(self) -> None:
        """PydanticAI exposes usage as ``result.usage()``, not an attribute."""
        original = SimpleNamespace(usage=lambda: SimpleNamespace(input_tokens=10, output_tokens=2))

        rebuilt = rebuild(record(original))

        self.assertEqual(rebuilt.usage().input_tokens, 10)

    def test_properties_are_probed_even_though_absent_from_dict(self) -> None:
        class WithProperty:
            @property
            def raw(self):
                return "from-property"

        rebuilt = rebuild(record(WithProperty()))

        self.assertEqual(rebuilt.raw, "from-property")

    def test_raising_property_is_skipped_not_fatal(self) -> None:
        class Exploding:
            def __init__(self):
                self.safe = "ok"

            @property
            def raw(self):
                raise RuntimeError("framework internals blew up")

        rebuilt = rebuild(record(Exploding()))

        self.assertEqual(rebuilt.safe, "ok")
        self.assertFalse(hasattr(rebuilt, "raw"))

    def test_recursion_is_bounded(self) -> None:
        node = SimpleNamespace(name="leaf")
        node.data = node  # self-referential, as framework graphs often are

        payload = record(node, max_depth=4)

        self.assertIn("truncated", str(payload))

    def test_callables_are_not_recorded_as_attributes(self) -> None:
        original = SimpleNamespace(raw="x", kickoff=lambda: "should not be captured")

        rebuilt = rebuild(record(original))

        self.assertEqual(rebuilt.raw, "x")
        self.assertFalse(hasattr(rebuilt, "kickoff"))


class RecordedObjectTests(unittest.TestCase):
    def test_repr_names_the_original_type(self) -> None:
        rebuilt = rebuild(record(SimpleNamespace(raw="x")))

        self.assertIsInstance(rebuilt, RecordedObject)
        self.assertIn("raw", repr(rebuilt))

    def test_iter_recorded_types_walks_the_graph(self) -> None:
        class CrewOutput:
            def __init__(self):
                self.tasks_output = [TaskOutput()]

        class TaskOutput:
            def __init__(self):
                self.messages = []

        types_found = set(iter_recorded_types(record(CrewOutput())))

        self.assertIn("CrewOutput", types_found)
        self.assertIn("TaskOutput", types_found)


if __name__ == "__main__":
    unittest.main()
