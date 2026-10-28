"""
The scenarios and checks shared by every evaluator in the interop study.

Taken from the same manifest the portability study runs through ECP's own runtime,
so all three evaluators (ECP runtime, Promptfoo, DeepEval) ask the same questions:
a reply criterion per scenario, the tool calls that must happen, and one that must not.
Writes scenarios.json for evaluators that run in other environments.
"""

import json
import shlex
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "portability"))
import make_manifests  # noqa: E402

FORBIDDEN = "issue_refund"


def load():
    manifest = yaml.safe_load(make_manifests.TEMPLATE.read_text(encoding="utf-8"))
    out = []
    for sc in manifest["scenarios"]:
        step = sc["steps"][0]
        judge = next(g for g in step["graders"] if g["type"] == "llm_judge")
        required = [
            {"name": g["tool_name"], "arguments": g.get("arguments") or {}}
            for g in step["graders"]
            if g["type"] == "tool_usage" and g.get("condition", "called") == "called"
        ]
        out.append({"name": sc["name"], "input": step["input"], "criterion": " ".join(judge["prompt"].split()),
                    "required": required})
    return out


def target(framework: str) -> str:
    agent = HERE.parent / "portability" / "agents" / f"agent_{framework}.py"
    return f"{shlex.quote(make_manifests.interpreter(framework).as_posix())} {shlex.quote(agent.as_posix())}"


if __name__ == "__main__":
    data = {"forbidden": FORBIDDEN, "scenarios": load(),
            "targets": {fw: target(fw) for fw in make_manifests.FRAMEWORKS}}
    (HERE / "scenarios.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"{len(data['scenarios'])} scenarios, {len(data['targets'])} targets -> scenarios.json")
