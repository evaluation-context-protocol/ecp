"""
Score the shared cases with DeepEval.

Reply family:  GEval, DeepEval's LLM-as-judge metric, using the same criterion text
               and the same model (claude-haiku-5-5) as the other tools. 3 repeats.
Trajectory:    two configurations, so DeepEval is not judged on its weakest setup:
                 A  ToolCorrectnessMetric for the required calls (arguments checked)
                    + ToolPermissionMetric(denied_tools) for the prohibition
                 B  ToolCorrectnessMetric(should_exact_match=True) alone - the way to
                    catch an unexpected call if you do not use the permission metric

Run in an environment with deepeval and anthropic. DeepEval and a current litellm
cannot share an environment (click<8.4 versus click>=8.4.2), which is why ECP's arm
runs elsewhere.
"""

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

from dotenv import load_dotenv  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RESULTS = HERE / "results"
load_dotenv(REPO / "examples" / "crewai_claude_crew" / ".env")

sys.path.insert(0, str(HERE))
import anthropic  # noqa: E402
import cases  # noqa: E402
from deepeval.metrics import GEval, ToolCorrectnessMetric, ToolPermissionMetric  # noqa: E402
from deepeval.models import DeepEvalBaseLLM  # noqa: E402
from deepeval.test_case import LLMTestCase, LLMTestCaseParams, ToolCall, ToolCallParams  # noqa: E402

MODEL = "claude-haiku-5-5"
REPEATS = 3
THRESHOLD = 0.5  # GEval returns a 0-1 score; at or above this counts as a pass


class AnthropicJudge(DeepEvalBaseLLM):
    """Back DeepEval's judge metrics with Claude instead of its default OpenAI model."""

    def __init__(self, model: str = MODEL):
        self._name = model
        self._client = anthropic.Anthropic()

    def load_model(self):
        return self._client

    def get_model_name(self) -> str:
        return self._name

    def generate(self, prompt: str, schema=None, *args, **kwargs):
        resp = self._client.messages.create(
            model=self._name, max_tokens=1024, messages=[{"role": "user", "content": prompt}]
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if schema is None:
            return text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        return schema(**json.loads(match.group(0))) if match else schema()

    async def a_generate(self, prompt: str, schema=None, *args, **kwargs):
        return self.generate(prompt, schema)


JUDGE = AnthropicJudge()


def geval_verdict(item):
    scenario, _label, _src, text = item
    try:
        metric = GEval(
            name="criterion",
            criteria=cases.CRITERIA[scenario],
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            model=JUDGE,
            threshold=THRESHOLD,
            async_mode=False,
        )
        metric.measure(LLMTestCase(input=cases.PROMPTS[scenario], actual_output=text))
        return {"pass": bool(metric.is_successful()), "score": metric.score}
    except Exception as exc:  # noqa: BLE001 - an errored call is data, not a crash
        return {"pass": None, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def to_calls(raw):
    return [ToolCall(name=c["name"], input_parameters=c["arguments"]) for c in raw]


def trajectory_verdicts():
    expected = to_calls(cases.REQUIRED)
    out = {}
    for cid, _expect, _desc, calls in cases.TRAJ_CASES:
        tc = LLMTestCase(
            input="x",
            actual_output="ok",
            tools_called=to_calls(calls),
            expected_tools=expected,
        )
        row = {}

        def run(label, metric):
            try:
                metric.measure(tc)
                row[label] = {"pass": bool(metric.is_successful()), "score": metric.score}
            except Exception as exc:  # noqa: BLE001
                row[label] = {"pass": None, "error": f"{type(exc).__name__}: {str(exc)[:140]}"}

        run(
            "required",
            ToolCorrectnessMetric(
                threshold=1.0,
                should_exact_match=False,
                should_consider_ordering=False,
                evaluation_params=[ToolCallParams.INPUT_PARAMETERS],
                async_mode=False,
                include_reason=False,
            ),
        )
        run(
            "denied",
            ToolPermissionMetric(denied_tools=list(cases.FORBIDDEN), include_reason=False),
        )
        run(
            "exact",
            ToolCorrectnessMetric(
                threshold=1.0,
                should_exact_match=True,
                evaluation_params=[ToolCallParams.INPUT_PARAMETERS],
                async_mode=False,
                include_reason=False,
            ),
        )
        # Configuration A passes only if both the required and the denied checks pass.
        a = [row["required"]["pass"], row["denied"]["pass"]]
        row["A"] = None if None in a else all(a)
        row["B"] = row["exact"]["pass"]
        out[cid] = row
    return out


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    items = cases.REPLY_CASES
    judge = []
    for _ in range(REPEATS):
        with ThreadPoolExecutor(max_workers=4) as pool:
            judge.append(list(pool.map(geval_verdict, items)))
    traj = trajectory_verdicts()

    import importlib.metadata as md

    payload = {
        "tool": "DeepEval",
        "versions": {"deepeval": md.version("deepeval"), "anthropic": md.version("anthropic")},
        "judge_model": MODEL,
        "geval_threshold": THRESHOLD,
        "reply": {"geval": judge},
        "traj": traj,
    }
    (RESULTS / "deepeval.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    errs = sum(1 for batch in judge for v in batch if v["pass"] is None)
    print(f"DeepEval scored {len(items)} replies (GEval x{REPEATS}, {errs} errored) and {len(traj)} trajectories")
    for cid, r in traj.items():
        def f(v):
            return "ERR " if v is None else ("PASS" if v else "FAIL")
        print(f"  {cid:22} A(required+denied)={f(r['A'])}  B(exact)={f(r['B'])}")
    if errs:
        first = next(v for batch in judge for v in batch if v["pass"] is None)
        print("first error:", first["error"])


if __name__ == "__main__":
    main()
