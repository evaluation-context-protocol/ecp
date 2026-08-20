# ECP Runtime

Reference runtime and CLI for the Evaluation Context Protocol (ECP).

ECP is a vendor-neutral protocol for testing agent outputs, tool calls, and evaluator-visible audit context across frameworks, models, eval platforms, and CI systems.

## Install

```bash
pip install "ecp-runtime==0.7.0"
```

## Usage

```bash
ecp init
ecp validate ecp_eval/manifest.yaml
ecp run --manifest ecp_eval/manifest.yaml --json
```

Run the flagship example:

```bash
ecp run --manifest examples/customer_support_demo/manifest.yaml --report report.html
```

Useful commands:

```bash
ecp validate examples/customer_support_demo/manifest.yaml
ecp conformance --target "python examples/customer_support_demo/agent.py"
ecp doctor
```

Manifest `target` values may be either a command for the default stdio transport or an ECP Streamable HTTP endpoint:

```yaml
target: "http://127.0.0.1:8765/ecp"
```

## Execution Boundaries

A hung agent must never pin a CI job. Two independent limits apply:

```bash
ecp run --manifest manifest.yaml --timeout 30 --max-duration 900
```

- `--timeout` (`ECP_RPC_TIMEOUT`, default 30s) bounds a single RPC.
- `--max-duration` (`ECP_MAX_DURATION`, unset by default) bounds the whole run. This is not redundant: an agent that answers just inside the per-RPC timeout on every step can still run for hours.

When a limit is breached, or the agent crashes or breaks the protocol, the run **degrades instead of aborting**. The failing step is recorded as failed, the rest of that scenario is marked skipped, and the next scenario starts with a fresh agent. Steps that never produced a result still count as failed checks, so a timeout can never be mistaken for a pass.

## Audit Record

Every run produces a structured audit payload, embedded under `audit` in the JSON report and writable standalone:

```bash
ecp run --manifest manifest.yaml --audit-out ecp_audit.json
```

It records the run id, timestamps, the manifest path and its SHA-256 digest, the resolved target, agent metadata, the configured limits, per-step latency and `exit_reason`, aggregated token usage, and pass/fail totals. Compare `totals.steps_planned` against `totals.steps_executed` to spot a run that degraded rather than one that genuinely passed. The schema is [`schema/audit.schema.json`](../../schema/audit.schema.json).

Agents can populate the token figures by returning `usage` from a step:

```python
Result(public_output="...", usage={"input_tokens": 1204, "output_tokens": 88})
```

If your manifest includes `llm_judge`, set an API key and optional judge model:

```bash
$env:OPENAI_API_KEY="your_key_here"
$env:ECP_LLM_JUDGE_MODEL="gpt-4o-mini"
```

## Links

- Documentation: https://evaluationcontextprotocol.io/
- Repository: https://github.com/evaluation-context-protocol/ecp
- Issues: https://github.com/evaluation-context-protocol/ecp/issues

