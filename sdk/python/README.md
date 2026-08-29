# ECP Python SDK

Python SDK for building agents that comply with the Evaluation Context Protocol (ECP).

ECP is a vendor-neutral protocol for testing agent outputs, tool calls, and evaluator-visible audit context across frameworks, models, eval platforms, and CI systems.

## Install

```bash
pip install "ecp-sdk==0.9.0"
```

Framework extras:

```bash
pip install "ecp-sdk[langchain]==0.9.0"
pip install "ecp-sdk[crewai]==0.9.0"
pip install "ecp-sdk[llamaindex]==0.9.0"
pip install "ecp-sdk[pydanticai]==0.9.0"
```

## Usage

```python
from ecp import Result, agent, on_step, serve


@agent(name="MyAgent")
class MyAgent:
    @on_step
    def step(self, user_input: str):
        return Result(
            public_output=f"Echo: {user_input}",
            evaluation_context="Echoed the input for evaluation.",
            tool_calls=[{"name": "echo", "arguments": {"text": user_input}}],
        )


if __name__ == "__main__":
    serve(MyAgent())
```

`evaluation_context` is the preferred field for evaluator-safe audit evidence. `private_thought` is still accepted as a deprecated compatibility alias.

## Async lifecycle hooks

`@on_step` and `@on_reset` may be synchronous functions or `async def` coroutines. The SDK awaits async hooks on one persistent event loop, so loop-bound clients and other async resources can be reused across requests.

```python
import asyncio

from ecp import Result, agent, on_reset, on_step, serve


@agent(name="AsyncAgent")
class AsyncAgent:
    @on_step
    async def step(self, user_input: str) -> Result:
        await asyncio.sleep(0.01)
        return Result(public_output=f"Processed: {user_input}")

    @on_reset
    async def reset(self) -> None:
        await asyncio.sleep(0)


if __name__ == "__main__":
    serve(AsyncAgent())
```

The same hooks work with `serve_http(...)`. See `examples/async_python_demo` for a runnable agent that supports either transport.

## Streamable HTTP

Agents can also run as an ECP Streamable HTTP server:

```python
if __name__ == "__main__":
    ecp.serve_http(MyAgent(), host="127.0.0.1", port=8765, path="/ecp")
```

The endpoint accepts JSON-RPC `POST` requests at `/ecp`. It returns JSON for requests, `202 Accepted` for notifications, and `405 Method Not Allowed` for `GET` SSE streams until ECP defines server-initiated messages.

## Testing Your Own Adapter

The bundled adaptors are a convenience, not a requirement - any framework works
if you return a `Result`. If you write your own, `ecp.testing` is the same
harness the built-in adaptors use, so you can pin its behaviour without
installing your framework in CI or holding API keys:

```python
from ecp.testing import record_fixture, replay

# Once, with the framework installed and credentials set:
fixture = record_fixture("crewai", crew, "What is 15 multiplied by 8?")
fixture.save("tests/fixtures/crew_calculator.json")

# Then in CI, offline:
from ecp.testing import AdapterFixture, diff_expected
assert diff_expected(AdapterFixture.load("tests/fixtures/crew_calculator.json")) == []
```

`record_fixture` captures the framework's real response object and the `Result`
your adapter produced from it. `replay` re-runs the adapter against that capture.
When a framework reshapes its internals, your `tool_calls` would otherwise go
quietly empty and every `tool_usage` grader would fail as if the agent had
regressed - this turns that into a clear test failure.

## Links

- Documentation: https://evaluationcontextprotocol.io/
- Repository: https://github.com/evaluation-context-protocol/ecp
- Issues: https://github.com/evaluation-context-protocol/ecp/issues
