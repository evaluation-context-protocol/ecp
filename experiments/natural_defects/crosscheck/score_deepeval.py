"""Score the saved crew runs with DeepEval (run in the DeepEval environment)."""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
HERE = Path(__file__).resolve().parent
H2H = HERE.parents[1] / "head_to_head"
sys.path.insert(0, str(H2H))

from deepeval.metrics import GEval, ToolPermissionMetric  # noqa: E402
from deepeval.test_case import LLMTestCase, LLMTestCaseParams, ToolCall  # noqa: E402
from run_deepeval import JUDGE, THRESHOLD  # noqa: E402  (same judge class and threshold as the head-to-head)

data = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))


def score(case):
    out = {"id": case["id"]}
    try:
        g = GEval(name="criterion", criteria=data["criterion"],
                  evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT], model=JUDGE,
                  threshold=THRESHOLD, async_mode=False)
        g.measure(LLMTestCase(input="customer request", actual_output=case["reply"]))
        out["reply_pass"] = bool(g.is_successful())
    except Exception as exc:  # noqa: BLE001
        out["reply_pass"], out["reply_error"] = None, f"{type(exc).__name__}: {str(exc)[:140]}"
    try:
        m = ToolPermissionMetric(denied_tools=data["forbidden"], include_reason=False)
        tc = LLMTestCase(input="x", actual_output="ok",
                         tools_called=[ToolCall(name=n) for n in case["reported_tools"]])
        m.measure(tc)
        out["tools_pass"] = bool(m.is_successful())
    except Exception as exc:  # noqa: BLE001
        out["tools_pass"], out["tools_error"] = None, f"{type(exc).__name__}: {str(exc)[:140]}"
    return out


with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(score, data["cases"]))
(HERE / "deepeval.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print("scored", len(results), "errors", sum(1 for r in results if None in (r["reply_pass"], r["tools_pass"])))
