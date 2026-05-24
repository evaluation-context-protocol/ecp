# Quickstart

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Docs Home](https://evaluationcontextprotocol.io/)

## 1. Install

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install "ecp-runtime==0.3.1" "ecp-sdk==0.3.1"
```

For framework demos, install the matching SDK extra:

```bash
pip install "ecp-sdk[langchain]==0.3.1" langchain-openai
pip install "ecp-sdk[crewai]==0.3.1" crewai
pip install "ecp-sdk[pydanticai]==0.3.1" pydantic-ai
pip install "ecp-sdk[llamaindex]==0.3.1" llama-index llama-index-llms-openai llama-index-tools-yahoo-finance
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

## Notes

- The current release line is `0.3.1`.
- New agents should use `evaluation_context`; `private_thought` remains a deprecated compatibility alias.
- Use `ECP_RPC_TIMEOUT` to control step timeouts. The default is 30 seconds.

