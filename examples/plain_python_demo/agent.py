import sys
from pathlib import Path

SDK_SRC = Path(__file__).resolve().parents[2] / "sdk" / "python" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from ecp import Result, agent, on_reset, on_step, serve


@agent(name="PlainPythonOpsBot")
class PlainPythonOpsBot:
    def __init__(self) -> None:
        self.handled_requests = 0

    @on_step
    def handle(self, user_input: str) -> Result:
        text = (user_input or "").strip()
        self.handled_requests += 1

        if text.lower().startswith("calc:"):
            expression = text.split(":", 1)[1].strip()
            answer = self._safe_eval(expression)
            return Result(
                public_output=f"Calculation result: {answer}",
                private_thought="Used the calculator helper for the requested arithmetic.",
                tool_calls=[
                    {
                        "name": "calculator",
                        "arguments": {"expression": expression},
                    }
                ],
            )

        if text.lower() == "policy:refund":
            return Result(
                public_output=(
                    "Refund policy: subscriptions can be refunded within 14 days "
                    "when no premium export has been used."
                ),
                private_thought="Answered directly from the in-app policy table.",
                tool_calls=[
                    {
                        "name": "policy_lookup",
                        "arguments": {"topic": "refund"},
                    }
                ],
            )

        return Result(
            status="done",
            public_output="Unsupported request. Use 'calc:' or 'policy:refund'.",
            private_thought="Returned a guided fallback for an unsupported command.",
        )

    @on_reset
    def reset(self) -> None:
        self.handled_requests = 0

    def _safe_eval(self, expression: str) -> str:
        allowed = set("0123456789+-*/(). ")
        if not expression or any(char not in allowed for char in expression):
            return "Invalid expression."

        try:
            result = eval(expression, {"__builtins__": {}})
        except Exception:
            return "Invalid expression."

        if isinstance(result, float) and result == int(result):
            return str(int(result))
        return str(result)


if __name__ == "__main__":
    serve(PlainPythonOpsBot())
