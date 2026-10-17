"""
EvalPort + ECP integration example.

EvalPort defines *what* to test as a portable JSON suite; ECP runs it against a
live agent. The agent is an ordinary ECP agent - it has no idea the scenarios
came from an EvalPort suite.
"""

import sys
from pathlib import Path

SDK_SRC = Path(__file__).resolve().parents[2] / "sdk" / "python" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from ecp import Result, agent, on_step, serve

ORDERS = {"A100": {"amount": "42.00", "days_since_purchase": 5}}
REFUND_WINDOW_DAYS = 30


@agent(name="EvalPortRefundAgent")
class EvalPortRefundAgent:
    @on_step
    def step(self, user_input: str) -> Result:
        text = (user_input or "").lower()

        if "how much" in text:
            return Result(
                public_output=" 42.00 ",  # padded on purpose: the suite sets strip
                evaluation_context="Read the stored order total.",
                tool_calls=[{"name": "lookup_order", "arguments": {"order_id": "A100"}}],
            )

        order = ORDERS["A100"]
        eligible = order["days_since_purchase"] <= REFUND_WINDOW_DAYS
        verdict = "eligible" if eligible else "not eligible"
        return Result(
            public_output=f"Order A100 is {verdict} for a refund.",
            evaluation_context=(
                f"Checked order A100: purchased {order['days_since_purchase']} days ago, "
                f"inside the {REFUND_WINDOW_DAYS}-day window."
            ),
            tool_calls=[
                {"name": "lookup_order", "arguments": {"order_id": "A100"}},
                {"name": "check_refund_policy", "arguments": {"order_id": "A100"}},
            ],
        )


if __name__ == "__main__":
    serve(EvalPortRefundAgent())
