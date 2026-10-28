"""
Generate Promptfoo configs from the shared cases, so Promptfoo is scored on exactly
the inputs ECP and DeepEval are.

Reply family:  `llm-rubric`, Promptfoo's LLM-as-judge assertion, with the same criterion
               text and the same model (claude-haiku-5-5).
Trajectory:    Promptfoo has no assertion for "this tool must not be called", so two
               configurations, each as its authors document it:
                 builtin  `tool-call-f1`, its built-in tool assertion (names as a set)
                 custom   a `javascript` assertion implementing the full policy
               plus `custom_prohibition`, the prohibition alone, to see how an
               empty tool-call report is treated.

The provider is Promptfoo's built-in `echo`, which returns the prompt unchanged, so
the "agent output" is exactly the case text with no model call in the way.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = json.loads((HERE / "results" / "cases.json").read_text(encoding="utf-8"))
GRADER = "file://anthropic_no_temp.js"


def dump(path: Path, doc: dict) -> None:
    # JSON is a valid YAML subset, which sidesteps quoting traps in free-form text.
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def reply_config() -> dict:
    tests = []
    for case in CASES["reply_cases"]:
        tests.append(
            {
                "vars": {"reply": case["text"]},
                "assert": [
                    {
                        "type": "llm-rubric",
                        "value": CASES["criteria"][case["scenario"]],
                        "provider": GRADER,
                    }
                ],
                "metadata": {"id": case["id"], "label": case["label"], "scenario": case["scenario"]},
            }
        )
    return {
        "description": "ECP head-to-head: reply family (llm-rubric)",
        "prompts": ["{{reply}}"],
        "providers": [{"id": "echo"}],
        "defaultTest": {"options": {"provider": GRADER}},
        "tests": tests,
    }


POLICY_JS = """
const out = JSON.parse(output);
const calls = out.tool_calls || [];
const required = %s;
const forbidden = %s;
const hasAll = required.every(r => calls.some(c => c.name === r.name &&
  Object.entries(r.arguments).every(([k, v]) => c.arguments && c.arguments[k] === v)));
const noForbidden = !calls.some(c => forbidden.includes(c.name));
return %s;
"""


def traj_config() -> dict:
    required = json.dumps(CASES["required"])
    forbidden = json.dumps(CASES["forbidden"])
    names = [c["name"] for c in CASES["required"]]

    variants = {
        "builtin": [{"type": "tool-call-f1", "value": names, "threshold": 1}],
        "custom": [{"type": "javascript", "value": POLICY_JS % (required, forbidden, "hasAll && noForbidden")}],
        "custom_prohibition": [{"type": "javascript", "value": POLICY_JS % (required, forbidden, "noForbidden")}],
    }
    tests = []
    for case in CASES["traj_cases"]:
        payload = json.dumps({"reply": "ok", "tool_calls": case["tool_calls"]})
        for name, asserts in variants.items():
            tests.append(
                {
                    "vars": {"payload": payload},
                    "assert": asserts,
                    "metadata": {"id": case["id"], "variant": name, "expect_pass": case["expect_pass"]},
                }
            )
    return {
        "description": "ECP head-to-head: trajectory family",
        "prompts": ["{{payload}}"],
        "providers": [{"id": "echo"}],
        "tests": tests,
    }


if __name__ == "__main__":
    dump(HERE / "promptfoo" / "reply.config.json", reply_config())
    dump(HERE / "promptfoo" / "traj.config.json", traj_config())
    print("wrote promptfoo/reply.config.json and promptfoo/traj.config.json")
