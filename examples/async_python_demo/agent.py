import asyncio
import os
import sys
from pathlib import Path

SDK_SRC = Path(__file__).resolve().parents[2] / "sdk" / "python" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from ecp import Result, agent, on_reset, on_step, serve, serve_http


@agent(name="AsyncResearchAgent")
class AsyncResearchAgent:
    def __init__(self) -> None:
        self.completed_requests = 0

    @on_step
    async def step(self, user_input: str) -> Result:
        query = (user_input or "").strip()
        await asyncio.sleep(0.01)
        self.completed_requests += 1
        return Result(
            public_output=f"Async research complete for: {query}",
            evaluation_context=(
                f"Awaited the research source and completed request #{self.completed_requests}."
            ),
            tool_calls=[{"name": "async_research", "arguments": {"query": query}}],
        )

    @on_reset
    async def reset(self) -> None:
        await asyncio.sleep(0)
        self.completed_requests = 0


if __name__ == "__main__":
    instance = AsyncResearchAgent()
    if os.environ.get("ECP_TRANSPORT", "stdio").lower() == "http":
        serve_http(
            instance,
            host=os.environ.get("ECP_HTTP_HOST", "127.0.0.1"),
            port=int(os.environ.get("ECP_HTTP_PORT", "8765")),
            path=os.environ.get("ECP_HTTP_PATH", "/ecp"),
        )
    else:
        serve(instance)
