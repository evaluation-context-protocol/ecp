import os
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.graders import check_llm_judge, check_tool_usage
from ecp_runtime.manifest import GraderConfig, StepConfig


class ToolUsageGraderTests(unittest.TestCase):
    def test_tool_usage_matches_subset_arguments(self) -> None:
        grader = GraderConfig(type="tool_usage", tool_name="calculator", arguments={"expression": "2+2"})
        calls = [{"name": "calculator", "arguments": {"expression": "2+2", "mode": "safe"}}]
        passed, reason = check_tool_usage(grader, calls)
        self.assertTrue(passed)
        self.assertIn("Found tool call", reason)

    def test_tool_usage_fails_when_no_calls(self) -> None:
        grader = GraderConfig(type="tool_usage", tool_name="calculator", arguments={})
        passed, reason = check_tool_usage(grader, [])
        self.assertFalse(passed)
        self.assertIn("No tool_calls present", reason)


class LLMJudgeTests(unittest.TestCase):
    def test_llm_judge_fails_without_api_key(self) -> None:
        grader = GraderConfig(type="llm_judge", prompt="Check quality.")
        with mock.patch.dict(os.environ, {}, clear=True):
            passed, reason, score = check_llm_judge(grader, "hello")
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)
        self.assertIn("OPENAI_API_KEY not set", reason)

    def test_llm_judge_uses_configured_model(self) -> None:
        calls = {}

        class _FakeCompletions:
            def create(self, **kwargs):
                calls["kwargs"] = kwargs
                msg = SimpleNamespace(content="Looks good. RESULT: PASS")
                choice = SimpleNamespace(message=msg)
                return SimpleNamespace(choices=[choice])

        class _FakeChat:
            completions = _FakeCompletions()

        class _FakeOpenAIClient:
            def __init__(self, api_key):
                self.api_key = api_key
                self.chat = _FakeChat()

        grader = GraderConfig(type="llm_judge", prompt="Check quality.")
        with mock.patch("ecp_runtime.graders.OpenAI", _FakeOpenAIClient):
            with mock.patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "test", "ECP_LLM_JUDGE_MODEL": "gpt-test-model"},
                clear=True,
            ):
                passed, _, score = check_llm_judge(grader, "hello")

        self.assertTrue(passed)
        self.assertEqual(score, 1.0)
        self.assertEqual(calls["kwargs"]["model"], "gpt-test-model")


class EvaluateStepSmokeTests(unittest.TestCase):
    def test_step_with_tool_usage(self) -> None:
        grader = GraderConfig(type="tool_usage", tool_name="calculator", arguments={})
        step = StepConfig(input="2+2", graders=[grader])
        result_obj = SimpleNamespace(public_output="4", private_thought=None, tool_calls=[{"name": "calculator", "arguments": {}}])
        # basic no-throw check through exported entrypoint
        from ecp_runtime.graders import evaluate_step

        checks = evaluate_step(step, result_obj)
        self.assertEqual(len(checks), 1)
        self.assertTrue(checks[0]["passed"])


if __name__ == "__main__":
    unittest.main()
