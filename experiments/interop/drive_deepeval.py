"""
DeepEval as the evaluator: the same checks, four agent frameworks, through the ECP bridge.

`ecp_runtime.integrations.deepeval.test_cases` runs each scenario on an ECP agent and
returns DeepEval test cases. Metrics, all DeepEval's own:

  reply       GEval with the scenario's criterion (same judge model as the other arms)
  required    ToolCorrectnessMetric with the required calls as expected_tools
  not_called  ToolPermissionMetric(denied_tools=["issue_refund"])

Run in the DeepEval environment, with ecp-runtime installed (pip install -e runtime/python --no-deps).
Usage: drive_deepeval.py --framework crewai [--reps 2] [--modes guarded eager]
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "head_to_head"))
sys.path.insert(0, str(HERE))

from deepeval.metrics import GEval, ToolCorrectnessMetric, ToolPermissionMetric  # noqa: E402
from deepeval.test_case import LLMTestCaseParams, ToolCall, ToolCallParams  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from drive_promptfoo import DATA, ground_truth  # noqa: E402
from ecp_runtime.integrations.deepeval import test_cases  # noqa: E402
from run_deepeval import JUDGE, THRESHOLD  # noqa: E402  (head_to_head's judge class and threshold)

load_dotenv(REPO / "examples" / "crewai_claude_crew" / ".env")


def verdict(metric, case):
    try:
        metric.measure(case)
        return bool(metric.is_successful()), None
    except Exception as exc:  # noqa: BLE001 - an errored metric is data
        return None, f"{type(exc).__name__}: {str(exc)[:160]}"


def run(framework, mode, rep):
    log = Path(tempfile.mkdtemp(prefix=f"de-{framework}-")) / "tools.jsonl"
    os.environ["ECP_TOOL_LOG"] = str(log)
    os.environ["ECP_PORTABILITY_MODE"] = mode
    rows = []
    for sc in DATA["scenarios"]:
        row = {"evaluator": "deepeval", "framework": framework, "mode": mode, "rep": rep, "scenario": sc["name"], "error": None}
        try:
            case = test_cases(DATA["targets"][framework], [sc["input"]], timeout=240)[0]
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            rows.append(row)
            continue
        case.expected_tools = [ToolCall(name=r["name"], input_parameters=r["arguments"]) for r in sc["required"]]
        geval = GEval(name="criterion", criteria=sc["criterion"], evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
                      model=JUDGE, threshold=THRESHOLD, async_mode=False)
        required = ToolCorrectnessMetric(threshold=1.0, should_exact_match=False, should_consider_ordering=False,
                                         evaluation_params=[ToolCallParams.INPUT_PARAMETERS], async_mode=False,
                                         include_reason=False)
        denied = ToolPermissionMetric(denied_tools=[DATA["forbidden"]], include_reason=False)
        row["reply_pass"], e1 = verdict(geval, case)
        row["required_pass"], e2 = verdict(required, case)
        row["not_called_pass"], e3 = verdict(denied, case)
        row["metric_errors"] = [e for e in (e1, e2, e3) if e]
        row["reply"] = case.actual_output
        row["reported_tools"] = [t.name for t in case.tools_called or []]
        rows.append(row)
    truth = ground_truth(log)
    for row, sc in zip(rows, DATA["scenarios"]):
        row["actual_tools"] = truth.get(sc["input"], [])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--framework", required=True)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--modes", nargs="*", default=["guarded", "eager"])
    args = ap.parse_args()
    out = HERE / "results" / f"deepeval_rows_{args.framework}.jsonl"
    out.parent.mkdir(exist_ok=True)
    done = set()
    if out.exists():
        done = {(r["mode"], r["rep"]) for r in map(json.loads, out.read_text(encoding="utf-8").splitlines())}
    for rep in range(args.reps):
        for mode in args.modes:
            if (mode, rep) in done:
                continue
            rows = run(args.framework, mode, rep)
            with open(out, "a", encoding="utf-8") as fh:
                fh.writelines(json.dumps(r) + "\n" for r in rows)
            print(f"{args.framework:11} {mode:8} rep {rep}: {len(rows)} steps", flush=True)


if __name__ == "__main__":
    main()
