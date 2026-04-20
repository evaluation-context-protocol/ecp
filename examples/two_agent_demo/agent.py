import sys
from pathlib import Path

SDK_SRC = Path(__file__).resolve().parents[2] / "sdk" / "python" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from ecp import Result, agent, on_reset, on_step, serve


class PlannerAgent:
    def plan(self, request: str) -> str:
        topic = request.strip()
        return (
            f"Plan for {topic}: "
            "1) confirm the goal, 2) highlight the current status, "
            "3) end with the immediate next step."
        )


class WriterAgent:
    def draft(self, request: str, plan: str) -> str:
        topic = request.strip()
        return (
            f"Launch note for {topic}: the goal is clear, the latest validation is green, "
            "and the next step is to share the report with the team."
        )


@agent(name="TwoAgentLaunchBot")
class TwoAgentLaunchBot:
    def __init__(self) -> None:
        self.planner = PlannerAgent()
        self.writer = WriterAgent()
        self.last_plan = ""

    @on_step
    def handle(self, user_input: str) -> Result:
        request = (user_input or "").strip()
        plan = self.planner.plan(request)
        draft = self.writer.draft(request, plan)
        self.last_plan = plan
        return Result(
            public_output=f"{draft}\n\nInternal workflow summary: {plan}",
            private_thought="Planner agent created a structure and writer agent turned it into a concise response.",
            tool_calls=[
                {"name": "planner_agent", "arguments": {"request": request}},
                {"name": "writer_agent", "arguments": {"request": request}},
            ],
        )

    @on_reset
    def reset(self) -> None:
        self.last_plan = ""


if __name__ == "__main__":
    serve(TwoAgentLaunchBot())
