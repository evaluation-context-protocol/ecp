import tempfile
import unittest
import sys
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

    def test_manifest_root_must_be_mapping(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
            tmp.write("- not: a mapping\n")
            tmp_path = tmp.name

        with self.assertRaises(ValueError):
            ECPManifest.from_yaml(tmp_path)


if __name__ == "__main__":
    unittest.main()
