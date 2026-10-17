"""
Tests for loading EvalPort suites as ECP scenarios.

The behaviour that matters most is the refusal: a suite using a grader ECP
cannot run must fail loudly at load time. Silently dropping it would produce a
confident pass rate for a check that never executed.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.evalport import (
    EvalPortError,
    describe_unmapped_fields,
    load_suite,
    suite_to_steps,
)
from ecp_runtime.graders import check_text_match
from ecp_runtime.manifest import ECPManifest, GraderConfig

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "evalport"
SUPPORTED = FIXTURES / "supported-suite.json"
UNSUPPORTED = FIXTURES / "unsupported-suite.json"


def _write(payload, suffix=".json"):
    tmp = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    json.dump(payload, tmp)
    tmp.close()
    return Path(tmp.name)


class LoadSuiteTests(unittest.TestCase):
    def test_loads_a_valid_suite(self) -> None:
        suite = load_suite(SUPPORTED)

        self.assertEqual(suite["id"], "suite_ecp_mapping")
        self.assertEqual(len(suite["test_cases"]), 6)

    def test_reads_utf8_regardless_of_platform_default(self) -> None:
        """Benchmark text routinely carries typographic punctuation."""
        path = _write({"version": "1.0.0", "id": "s", "test_cases": [
            {"id": "t", "input": "Janet’s ducks — how many?", "expected_output": "9",
             "graders": [{"id": "g", "type": "exact_match"}]}
        ]})

        suite = load_suite(path)

        self.assertIn("’", suite["test_cases"][0]["input"])

    def test_rejects_malformed_and_incomplete_suites(self) -> None:
        bad_json = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        bad_json.write("{not json")
        bad_json.close()
        with self.assertRaisesRegex(EvalPortError, "not valid JSON"):
            load_suite(bad_json.name)

        with self.assertRaisesRegex(EvalPortError, "not readable"):
            load_suite(FIXTURES / "does-not-exist.json")

        for payload, expected in (
            ({"id": "s", "test_cases": [{}]}, "version"),
            ({"version": "1.0.0", "test_cases": [{}]}, "'id'"),
            ({"version": "1.0.0", "id": "s", "test_cases": []}, "no test_cases"),
            ({"version": "1.0.0", "id": "s", "test_cases_file": "cases.jsonl"}, "test_cases_file"),
        ):
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(EvalPortError, expected):
                    load_suite(_write(payload))


class GraderMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.steps = suite_to_steps(load_suite(SUPPORTED), source="supported-suite.json")

    def test_exact_match_carries_comparison_options(self) -> None:
        """EvalPort's ignore_case/strip must survive, or semantics silently change."""
        grader = self.steps[0]["graders"][0]

        self.assertEqual(
            grader,
            {
                "type": "text_match",
                "field": "public_output",
                "condition": "equals",
                "value": "120",
                "ignore_case": True,
                "strip": True,
            },
        )

    def test_contains_uses_params_substring(self) -> None:
        grader = next(s["graders"][0] for s in self.steps if s["input"] == "Refund for A100?")

        self.assertEqual(grader["condition"], "contains")
        self.assertEqual(grader["value"], "eligible")

    def test_regex_flags_are_folded_into_the_pattern(self) -> None:
        """ECP calls re.search without flags, so they become an inline group."""
        grader = next(s["graders"][0] for s in self.steps if s["input"] == "Which order?")

        self.assertEqual(grader["condition"], "regex")
        self.assertEqual(grader["pattern"], "(?i)ORDER-[0-9]+")

    def test_llm_judge_maps_prompt(self) -> None:
        grader = next(s["graders"][0] for s in self.steps if s["input"] == "Explain the policy")

        self.assertEqual(grader["type"], "llm_judge")
        self.assertEqual(grader["prompt"], "Does it cite a policy?")

    def test_inline_graders_and_expected_tools_both_map(self) -> None:
        step = next(s for s in self.steps if s["input"] == "Refund order A100")
        types = [g["type"] for g in step["graders"]]

        self.assertEqual(types, ["text_match", "tool_usage", "tool_usage"])
        self.assertEqual(
            [g["tool_name"] for g in step["graders"] if g["type"] == "tool_usage"],
            ["lookup_order", "check_refund_policy"],
        )

    def test_multi_turn_input_grades_only_the_final_turn(self) -> None:
        """Earlier turns are setup; EvalPort grades the case's final output."""
        turns = [s for s in self.steps if s["input"] in ("Hello", "I want a refund", "Order A100")]

        self.assertEqual(len(turns), 3)
        self.assertEqual([bool(t["graders"]) for t in turns], [False, False, True])

    def test_every_mapped_grader_is_a_valid_ecp_grader(self) -> None:
        """The mapping must produce graders the runtime actually accepts."""
        for step in self.steps:
            for grader in step["graders"]:
                with self.subTest(grader=grader):
                    GraderConfig(**grader)


class UnsupportedGraderTests(unittest.TestCase):
    def test_unsupported_graders_are_refused_not_dropped(self) -> None:
        with self.assertRaises(EvalPortError) as ctx:
            suite_to_steps(load_suite(UNSUPPORTED), source="unsupported-suite.json")

        message = str(ctx.exception)
        # Name every offender and say why refusing beats running.
        self.assertIn("2 test case(s)", message)
        self.assertIn("semantic_similarity", message)
        self.assertIn("code", message)
        self.assertIn("never ran", message)

    def test_unknown_grader_type_is_also_refused(self) -> None:
        suite = {
            "version": "1.0.0",
            "id": "s",
            "test_cases": [
                {"id": "t", "input": "x", "graders": [{"id": "g", "type": "trulens_feedback"}]}
            ],
        }

        with self.assertRaisesRegex(EvalPortError, "trulens_feedback"):
            suite_to_steps(suite, source="s")

    def test_dangling_grader_reference_is_an_error(self) -> None:
        suite = {
            "version": "1.0.0",
            "id": "s",
            "test_cases": [{"id": "t", "input": "x", "graders": ["gr_missing"]}],
        }

        with self.assertRaisesRegex(EvalPortError, "unknown grader id"):
            suite_to_steps(suite, source="s")

    def test_exact_match_without_expected_output_is_an_error(self) -> None:
        suite = {
            "version": "1.0.0",
            "id": "s",
            "test_cases": [{"id": "t", "input": "x", "graders": [{"id": "g", "type": "exact_match"}]}],
        }

        with self.assertRaisesRegex(EvalPortError, "expected_output"):
            suite_to_steps(suite, source="s")

    def test_unmappable_regex_flags_are_an_error(self) -> None:
        suite = {
            "version": "1.0.0",
            "id": "s",
            "test_cases": [
                {
                    "id": "t",
                    "input": "x",
                    "graders": [
                        {"id": "g", "type": "regex", "params": {"pattern": "a", "flags": "z"}}
                    ],
                }
            ],
        }

        with self.assertRaisesRegex(EvalPortError, "cannot be mapped"):
            suite_to_steps(suite, source="s")


class UnmappedFieldReportingTests(unittest.TestCase):
    def test_pinned_judge_model_is_reported(self) -> None:
        """EvalPort pins the judge for comparability; ECP reads it from the env."""
        notes = describe_unmapped_fields(load_suite(SUPPORTED))

        self.assertTrue(any("gpt-4o-mini" in n and "ECP_LLM_JUDGE_MODEL" in n for n in notes))

    def test_inert_fields_are_reported_but_not_fatal(self) -> None:
        suite = {
            "version": "1.0.0",
            "id": "s",
            "config": {"provider": {"model": "gpt-4o"}},
            "test_cases": [
                {
                    "id": "t",
                    "input": "x",
                    "expected_output": "y",
                    "weight": 2.0,
                    "timeout_ms": 5000,
                    "context": ["doc"],
                    "graders": [{"id": "g", "type": "exact_match"}],
                }
            ],
        }

        notes = describe_unmapped_fields(suite)

        joined = " | ".join(notes)
        for expected in ("weight", "timeout_ms", "provider", "context"):
            self.assertIn(expected, joined)
        # Reporting only; the suite still loads.
        self.assertEqual(len(suite_to_steps(suite, source="s")), 1)


class TextMatchOptionsTests(unittest.TestCase):
    """The grader options the EvalPort mapping depends on."""

    def test_strip_and_ignore_case_apply_to_both_operands(self) -> None:
        grader = GraderConfig(
            type="text_match", condition="equals", value=" Eighteen ", ignore_case=True, strip=True
        )

        passed, _ = check_text_match(grader, "  eighteen  ")

        self.assertTrue(passed)

    def test_defaults_remain_byte_exact(self) -> None:
        """Existing manifests must not change meaning."""
        grader = GraderConfig(type="text_match", condition="equals", value="18")

        self.assertFalse(check_text_match(grader, " 18 ")[0])
        self.assertTrue(check_text_match(grader, "18")[0])

    def test_contains_respects_ignore_case(self) -> None:
        grader = GraderConfig(
            type="text_match", condition="contains", value="ELIGIBLE", ignore_case=True
        )

        self.assertTrue(check_text_match(grader, "the order is eligible")[0])


class ManifestIntegrationTests(unittest.TestCase):
    def test_manifest_loads_an_evalport_dataset_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "suite.json").write_text(
                SUPPORTED.read_text(encoding="utf-8"), encoding="utf-8"
            )
            (tmp / "manifest.yaml").write_text(
                'manifest_version: "v1"\n'
                'name: "EvalPort import"\n'
                'target: "python agent.py"\n'
                "scenarios:\n"
                '  - name: "Imported"\n'
                "    dataset:\n"
                '      type: "evalport"\n'
                '      source: "suite.json"\n',
                encoding="utf-8",
            )

            manifest = ECPManifest.from_yaml(str(tmp / "manifest.yaml"))

        scenario = manifest.scenarios[0]
        # 5 single-turn cases + 3 turns from the multi-turn case.
        self.assertEqual(len(scenario.steps), 8)
        # 4 single graders + (1 inline + 2 expected_tools) + 1 on the final turn.
        self.assertEqual(sum(len(s.graders) for s in scenario.steps), 8)

    def test_manifest_surfaces_unsupported_graders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "suite.json").write_text(
                UNSUPPORTED.read_text(encoding="utf-8"), encoding="utf-8"
            )
            (tmp / "manifest.yaml").write_text(
                'manifest_version: "v1"\n'
                'name: "Bad import"\n'
                'target: "python agent.py"\n'
                "scenarios:\n"
                '  - name: "Imported"\n'
                "    dataset:\n"
                '      type: "evalport"\n'
                '      source: "suite.json"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(EvalPortError, "semantic_similarity"):
                ECPManifest.from_yaml(str(tmp / "manifest.yaml"))


if __name__ == "__main__":
    unittest.main()
