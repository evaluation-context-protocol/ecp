"""
A deterministic stand-in for the live LangChain agent.

Exists to validate the study's measurement logic without spending API calls:
it really invokes the instrumented tools (so the ground-truth log is populated)
but deliberately UNDER-REPORTS one of them through ECP. If the harness cannot
detect that gap, its fidelity numbers mean nothing.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python" / "src"))
sys.path.insert(0, str(HERE))

import domain  # noqa: E402
from ecp import Result, agent, on_step, serve  # noqa: E402


@agent(name="StubRefundAgent", capabilities={"tool_calls": {}, "evaluation_context": {}})
class StubRefundAgent:
    @on_step
    def step(self, user_input: str) -> Result:
        order_id = "A100"
        for candidate in domain.ORDERS:
            if candidate.lower() in (user_input or "").lower():
                order_id = candidate
                break

        # Both tools genuinely run, so both land in the ground-truth log.
        detail = domain.lookup_order(order_id)
        policy = domain.check_refund_policy(order_id)
        eligible = "within" in policy
        total = domain.ORDERS[order_id]["total"]
        verdict = "eligible" if eligible else "not eligible"

        return Result(
            public_output=f"Order {order_id} is {verdict} for a refund of ${total}.",
            evaluation_context=f"{detail} {policy}",
            # Deliberate under-report: check_refund_policy is omitted.
            tool_calls=[{"name": "lookup_order", "arguments": {"order_id": order_id}}],
        )


if __name__ == "__main__":
    serve(StubRefundAgent())
