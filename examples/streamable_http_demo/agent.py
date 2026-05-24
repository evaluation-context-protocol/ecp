import os
import sys
from pathlib import Path

SDK_SRC = Path(__file__).resolve().parents[2] / "sdk" / "python" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from ecp import Result, agent, on_reset, on_step, serve_http


@agent(name="StreamableHTTPDemoBot")
class StreamableHTTPDemoBot:
    def __init__(self) -> None:
        self.step_count = 0

    @on_step
    def handle(self, user_input: str) -> Result:
        self.step_count += 1
        text = (user_input or "").strip()

        if text.lower().startswith("echo:"):
            message = text.split(":", 1)[1].strip()
            return Result(
                public_output=f"Echo over HTTP: {message}",
                evaluation_context="Handled the request through the Streamable HTTP transport.",
                tool_calls=[
                    {
                        "name": "http_echo",
                        "arguments": {"message": message},
                    }
                ],
            )

        return Result(
            public_output="Unsupported request. Use 'echo: <message>'.",
            evaluation_context="Returned a guided fallback for an unsupported command.",
        )

    @on_reset
    def reset(self) -> None:
        self.step_count = 0


if __name__ == "__main__":
    host = os.environ.get("ECP_HTTP_HOST", "127.0.0.1")
    port = int(os.environ.get("ECP_HTTP_PORT", "8765"))
    path = os.environ.get("ECP_HTTP_PATH", "/ecp")
    serve_http(StreamableHTTPDemoBot(), host=host, port=port, path=path)
