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
python -m ecp_runtime.cli run --manifest examples/plain_python_demo/manifest.yaml --json
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
python -m ecp_runtime.cli run --manifest examples/two_agent_demo/manifest.yaml --json
```

## Honest DX Verdict

What feels good today:

- the protocol loop is small and understandable
- a plain app integration is very little code
- manifests are readable and easy to reason about
- the runtime gives a usable pass/fail result without much setup

What still feels rough:

- `target` commands are still working-directory sensitive unless written carefully
- there is no dedicated `validate` CLI yet for fast manifest checking
- richer diagnostics and report detail would improve debugging when integrations fail

## Bottom Line

Yes, ECP can already be used with a small application and with a simple 1-2 agent workflow. The current developer experience is credible for lightweight integrations, but it would get meaningfully better with manifest validation, stronger diagnostics, and richer runtime/report output.
