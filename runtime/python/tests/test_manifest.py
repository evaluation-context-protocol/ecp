import sys
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.manifest import ECPManifest, GraderConfig


class ManifestValidationTests(unittest.TestCase):
    def test_text_match_requires_condition(self) -> None:
        with self.assertRaises(ValidationError):
            GraderConfig(type="text_match")

    def test_text_match_regex_requires_pattern(self) -> None:
        with self.assertRaises(ValidationError):
            GraderConfig(type="text_match", condition="regex")

    def test_text_match_contains_requires_value(self) -> None:
        with self.assertRaises(ValidationError):
            GraderConfig(type="text_match", condition="contains")

    def test_llm_judge_requires_prompt(self) -> None:
        with self.assertRaises(ValidationError):
            GraderConfig(type="llm_judge")

    def test_invalid_grader_type_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            GraderConfig(type="unknown")  # type: ignore[arg-type]

    def test_evaluation_context_field_allowed(self) -> None:
        grader = GraderConfig(
            type="text_match",
            field="evaluation_context",
            condition="contains",
            value="checked",
        )

        self.assertEqual(grader.field, "evaluation_context")

    def test_manifest_root_must_be_mapping(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
            tmp.write("- not: a mapping\n")
            tmp_path = tmp.name

        with self.assertRaises(ValueError):
            ECPManifest.from_yaml(tmp_path)

    def test_unknown_manifest_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ECPManifest(
                manifest_version="v1",
                name="test",
                target="python agent.py",
                scenarios=[],
                unexpected=True,
            )

    def test_unknown_grader_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            GraderConfig(
                type="text_match",
                condition="contains",
                value="ok",
                unexpected=True,
            )


if __name__ == "__main__":
    unittest.main()
