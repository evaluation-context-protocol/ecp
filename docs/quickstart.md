# Quickstart

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Docs Home](https://evaluationcontextprotocol.io/)

## 1. Install

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install "ecp-runtime==0.8.0" "ecp-sdk==0.8.0"
```

For framework demos, install the matching SDK extra:

```bash
pip install "ecp-sdk[langchain]==0.8.0" langchain-openai
pip install "ecp-sdk[crewai]==0.8.0" crewai
pip install "ecp-sdk[pydanticai]==0.8.0" pydantic-ai
pip install "ecp-sdk[llamaindex]==0.8.0" llama-index llama-index-llms-openai llama-index-tools-yahoo-finance
```

## 2. Create A Starter Eval

```bash
ecp init
ecp validate ecp_eval/manifest.yaml
ecp run --manifest ecp_eval/manifest.yaml --json
```

## 3. Run The Flagship Demo

The customer support demo checks final output, required tool calls, and evaluator-safe audit context.

```bash
ecp validate examples/customer_support_demo/manifest.yaml
ecp run --manifest examples/customer_support_demo/manifest.yaml --report report.html
```

## 4. Run A Framework Demo

```bash
ecp run --manifest examples/langchain_demo/manifest.yaml
```

Other manifests live in:

- `examples/plain_python_demo/manifest.yaml`
- `examples/two_agent_demo/manifest.yaml`
- `examples/crewai_demo/manifest.yaml`
- `examples/pydantic_ai_demo/manifest.yaml`
- `examples/llamaindex_demo/manifest.yaml`

## 5. JSON Output For CI

Print a JSON report:

```bash
ecp run --manifest examples/customer_support_demo/manifest.yaml --json
```

Save a JSON report:

```bash
ecp run --manifest examples/customer_support_demo/manifest.yaml --json-out report.json
```

By default, `ecp run` exits non-zero when checks fail. Use `--no-fail-on-error` when you want a report without failing the process.

## 6. Optional LLM Judge

If your manifest uses `llm_judge`, set:

```bash
$env:OPENAI_API_KEY="your_key_here"
$env:ECP_LLM_JUDGE_MODEL="gpt-4o-mini"
$env:ECP_LLM_JUDGE_TEMPERATURE="0"
```

## 7. Streamable HTTP

Start the HTTP agent:

```bash
python examples/streamable_http_demo/agent.py
```

Run the HTTP-target manifest:

```bash
ecp run --manifest examples/streamable_http_demo/manifest.yaml --json
```

## 8. Inspector

```bash
npm run inspector
```

Open `http://127.0.0.1:6274`.

## 9. Conformance Smoke Test

For protocol implementers:

```bash
ecp conformance --target "python examples/customer_support_demo/agent.py"
```

For long-running agent calls, set a timeout explicitly:

```bash
ecp run --manifest manifest.yaml --timeout 60
ecp conformance --target "python agent.py" --timeout 60
```

## 10. Execution Boundaries

A hung agent must never pin a CI job. Bound a run from both directions:

```bash
ecp run --manifest manifest.yaml --timeout 30 --max-duration 900
```

`--timeout` bounds a single RPC; `--max-duration` bounds the whole run. Both are needed: an agent that answers just inside the per-RPC timeout on every step can still run for hours.

When either limit trips, or the agent crashes, the run **degrades instead of aborting**. The failing step is recorded as failed, the rest of that scenario is skipped, and the next scenario runs against a fresh agent, so you still get a full report:

```
Step 1: PASS
FAIL | step 2 did not complete (timeout): Agent response timed out after 3.0s
Scenario: Healthy scenario after the hang
Step 1: PASS
Run Complete. Passed: 2/4   exit_reason=timeout
```

Steps that never produced a result still count as failed checks, so a timeout cannot be mistaken for a pass.

## 11. Audit Record

Every run emits a structured audit payload, embedded under `audit` in the JSON report and writable standalone:

```bash
ecp run --manifest manifest.yaml --audit-out ecp_audit.json
```

It captures the run id, timestamps, the manifest SHA-256 digest, agent metadata, configured limits, per-step latency and `exit_reason`, token usage, and pass/fail totals. Compare `totals.steps_planned` with `totals.steps_executed` to tell a clean run from a degraded one.

Agents populate the token figures by returning `usage` from a step:

```python
Result(
    public_output="Order A100 is eligible for a refund.",
    evaluation_context="Checked order A100 against the 30-day window.",
    usage={"input_tokens": 1204, "output_tokens": 88},
)
```

Omit `usage` entirely if your agent cannot observe token counts; the runtime distinguishes "not reported" from "reported as zero".

## Notes

- The current release line is `0.8.0`.
- New agents should use `evaluation_context`; `private_thought` remains a deprecated compatibility alias.
- `--timeout` controls the RPC timeout for `run` and `conformance`. It overrides `ECP_RPC_TIMEOUT`; the default is 30 seconds.
- `--max-duration` caps total run time. It overrides `ECP_MAX_DURATION` and is unset by default.
- `--audit-out` writes the audit payload to its own file. The same payload is always present under `audit` in `--json` / `--json-out` output.
- Python SDK `@on_step` and `@on_reset` hooks may be synchronous or `async def` functions.
