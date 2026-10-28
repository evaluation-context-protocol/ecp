"""Promptfoo config over the saved crew runs: llm-rubric on the reply, javascript on the tool calls."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
GRADER = "file://../../head_to_head/promptfoo/anthropic_no_temp.js"

JS = """
const calls = JSON.parse(output).tool_calls || [];
return !calls.some(n => %s.includes(n));
""" % json.dumps(data["forbidden"])

tests = []
for c in data["cases"]:
    tests.append({"vars": {"payload": c["reply"]}, "options": {"provider": GRADER},
                  "assert": [{"type": "llm-rubric", "value": data["criterion"], "provider": GRADER}],
                  "metadata": {"id": c["id"], "kind": "reply"}})
    tests.append({"vars": {"payload": json.dumps({"tool_calls": c["reported_tools"]})},
                  "assert": [{"type": "javascript", "value": JS}],
                  "metadata": {"id": c["id"], "kind": "tools"}})
config = {"description": "saved crew runs", "prompts": ["{{payload}}"], "providers": [{"id": "echo"}],
          "defaultTest": {"options": {"provider": GRADER}}, "tests": tests}
(HERE / "promptfoo.config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
print(len(tests), "tests")
