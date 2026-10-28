"""
Prohibition on its own: what happens when the agent reports no tool calls at all?

A prohibition ("this tool must not be called") passes when the forbidden call is
absent, so an empty report satisfies it. That is correct if the agent really made no
calls, and dangerous if the adapter simply failed to report them: the check cannot
tell the two apart from the report alone.

ECP's `not_called` handles this by requiring the agent to have declared the
`tool_calls` capability. This script records ECP's verdict in both situations so the
other tools' behaviour on the same input can be read against it. No API calls.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cases  # noqa: E402
from ecp_runtime.graders import evaluate_step  # noqa: E402
from ecp_runtime.manifest import GraderConfig, StepConfig  # noqa: E402

step = StepConfig(
    input="x",
    graders=[GraderConfig(type="tool_usage", condition="not_called", tool_name=n) for n in cases.FORBIDDEN],
)


def verdict(calls, declared):
    result = SimpleNamespace(public_output="ok", evaluation_context=None, private_thought=None, tool_calls=calls)
    checks = evaluate_step(step, result, declared_capabilities=declared)
    return all(c["passed"] for c in checks), checks[0]["reasoning"][:110]


out = {}
for cid, _exp, _desc, calls in cases.TRAJ_CASES:
    declared_pass, _ = verdict(calls, {"tool_calls": {}})
    undeclared_pass, why = verdict(calls, {})
    out[cid] = {"declared": declared_pass, "undeclared": undeclared_pass, "undeclared_reason": why}

(HERE / "results" / "ecp_prohibition.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
for cid, v in out.items():
    print(f"  {cid:22} declared={'PASS' if v['declared'] else 'FAIL'}  undeclared={'PASS' if v['undeclared'] else 'FAIL'}")
