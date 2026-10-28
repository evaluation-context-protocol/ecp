"""
Score the shared cases with ECP.

Reply family:  the regexes the earlier manifest used, and ECP's llm_judge (3 repeats).
Trajectory:    ECP's own graders - tool_usage for the two required calls, plus a
               not_called prohibition on issue_refund - exactly as a manifest would
               declare them, run through ECP's real grading function.

Run in an environment that has ecp-runtime and a current litellm.
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RESULTS = HERE / "results"
load_dotenv(REPO / "examples" / "crewai_claude_crew" / ".env")
os.environ["ECP_LLM_JUDGE_MODEL"] = "anthropic/claude-haiku-5-5"

sys.path.insert(0, str(HERE))
import cases  # noqa: E402
from ecp_runtime.graders import check_llm_judge, check_text_match, evaluate_step  # noqa: E402
from ecp_runtime.manifest import GraderConfig, StepConfig  # noqa: E402

REPEATS = 3


def regex_verdict(scenario: str, text: str) -> bool:
    for spec in cases.SHIPPED_REGEX[scenario]:
        grader = GraderConfig(type="text_match", condition="regex", pattern=spec["pattern"])
        if not check_text_match(grader, text)[0]:
            return False
    return True


def judge_verdict(item):
    scenario, _label, _src, text = item
    grader = GraderConfig(type="llm_judge", prompt=cases.CRITERIA[scenario])
    passed, reasoning, _ = check_llm_judge(grader, text)
    errored = reasoning.startswith(("LLM Judge Error", "LLM judge unavailable"))
    return None if errored else passed


def trajectory_verdicts():
    graders = [
        GraderConfig(type="tool_usage", tool_name=c["name"], arguments=c["arguments"])
        for c in cases.REQUIRED
    ] + [
        GraderConfig(type="tool_usage", condition="not_called", tool_name=name)
        for name in cases.FORBIDDEN
    ]
    step = StepConfig(input="x", graders=graders)
    out = {}
    for cid, _expect, _desc, calls in cases.TRAJ_CASES:
        result = SimpleNamespace(
            public_output="ok", evaluation_context=None, private_thought=None, tool_calls=calls
        )
        checks = evaluate_step(step, result, declared_capabilities={"tool_calls": {}})
        out[cid] = {
            "pass": all(c["passed"] for c in checks),
            "failed": [c["reasoning"][:90] for c in checks if not c["passed"]],
        }
    return out


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    items = cases.REPLY_CASES
    regex = [regex_verdict(s, t) for s, _l, _src, t in items]
    judge = []
    for _ in range(REPEATS):
        with ThreadPoolExecutor(max_workers=4) as pool:
            judge.append(list(pool.map(judge_verdict, items)))
    traj = trajectory_verdicts()

    import importlib.metadata as md

    payload = {
        "tool": "ECP",
        "versions": {"ecp-runtime": md.version("ecp-runtime"), "litellm": md.version("litellm")},
        "judge_model": os.environ["ECP_LLM_JUDGE_MODEL"],
        "reply": {"regex": regex, "judge": judge},
        "traj": traj,
    }
    (RESULTS / "ecp.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    errs = sum(v is None for batch in judge for v in batch)
    print(f"ECP scored {len(items)} replies (regex + judge x{REPEATS}, {errs} judge errors) and {len(traj)} trajectories")
    for cid, v in traj.items():
        print(f"  {cid:22} {'PASS' if v['pass'] else 'FAIL'}  {v['failed'][0] if v['failed'] else ''}")


if __name__ == "__main__":
    main()
