# Developer Experience Validation

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Docs Home](https://evaluationcontextprotocol.io/)

This page checks the question: can ECP be used smoothly with a small application, not just a framework-specific demo?

## Validation Setups

### 1. Plain Python app

Files:

- `examples/plain_python_demo/agent.py`
- `examples/plain_python_demo/manifest.yaml`

What it proves:

- you can integrate ECP with a plain Python application using only `@agent`, `@on_step`, `@on_reset`, `Result`, and `serve(...)`
- no LangChain, CrewAI, PydanticAI, or LlamaIndex adapter is required
- runtime grading and reporting still work the same way

Run it:

```bash
ecp run --manifest examples/plain_python_demo/manifest.yaml --json
```

### 2. Two-agent workflow app

Files:

- `examples/two_agent_demo/agent.py`
- `examples/two_agent_demo/manifest.yaml`

What it proves:

- ECP can sit on top of a small multi-agent style application
- internal planner/writer coordination can be surfaced through `tool_calls`
- the runtime can evaluate the workflow using the same manifest format

Run it:

```bash
ecp run --manifest examples/two_agent_demo/manifest.yaml --json
```

### 3. Streamable HTTP transport app

Files:

- `examples/streamable_http_demo/agent.py`
- `examples/streamable_http_demo/manifest.yaml`

What it proves:

- an ECP agent can run as a long-lived HTTP service instead of a child process
- the runtime can evaluate a manifest whose `target` is an HTTP endpoint
- JSON-RPC request/response behavior remains the same from the grader's point of view

Run it in terminal 1:

```bash
python examples/streamable_http_demo/agent.py
```

Run the evaluation in terminal 2:

```bash
ecp run --manifest examples/streamable_http_demo/manifest.yaml --json
```

Optional direct transport smoke test:

```bash
curl -i http://127.0.0.1:8765/ecp ^
  -H "Accept: application/json, text/event-stream" ^
  -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"agent/step\",\"params\":{\"input\":\"echo: hello\"}}"
```

## Honest DX Verdict

What feels good today:

- the protocol loop is small and understandable
- a plain app integration is very little code
- manifests are readable and easy to reason about
- the runtime gives a usable pass/fail result without much setup
- Streamable HTTP can be tested with the same manifest/grader flow as stdio

What still feels rough:

- `target` commands are still working-directory sensitive unless written carefully
- there is no dedicated `validate` CLI yet for fast manifest checking
- richer diagnostics and report detail would improve debugging when integrations fail
- the HTTP server must be started separately before running an HTTP-target manifest

## Bottom Line

Yes, ECP can already be used with a small application, with a simple 1-2 agent workflow, and with a Streamable HTTP agent service. The current developer experience is credible for lightweight integrations, but it would get meaningfully better with manifest validation, stronger diagnostics, richer runtime/report output, and a helper command for launching HTTP agents.
