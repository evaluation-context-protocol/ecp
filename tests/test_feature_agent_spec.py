import unittest
from pathlib import Path


FEATURE_AGENT_PATH = Path(".github/agents/feature agent.agent.md")


class FeatureAgentSpecTests(unittest.TestCase):
    def test_feature_agent_contract_sections_present(self):
        text = FEATURE_AGENT_PATH.read_text(encoding="utf-8").lower()
        required_phrases = [
            "inputs",
            "required outputs",
            "code changes",
            "tests",
            "docs updates",
            "validation commands",
            "pr summary",
            "definition of done",
            "migration notes",
            "blocked",
            "root cause",
        ]
        for phrase in required_phrases:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
