# ECP Inspector

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Docs Home](https://evaluationcontextprotocol.io/)

ECP Inspector is a local developer UI for testing and debugging ECP agents. It follows the same workflow shape as MCP Inspector: connect to a target, inspect capabilities, send protocol requests, run scenarios, and watch logs.

## Start

```bash
npm run inspector
```

Open `http://127.0.0.1:6274`.

## What It Shows

- Evaluation manifests discovered from `examples/**/manifest.yaml`
- A connection pane for stdio command targets and Streamable HTTP endpoints
- Scenario and grader details from each manifest
- A step tester for sending `agent/step`
- Evaluation run results from the ECP runtime
- Protocol notifications and logs

## Streamable HTTP Check

Start the HTTP demo agent in one terminal:

```bash
python examples/streamable_http_demo/agent.py
```

Start the inspector in another terminal:

```bash
npm run inspector
```

Select `Streamable HTTP Transport Validation`, connect, and send a step.
