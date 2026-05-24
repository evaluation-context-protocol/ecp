# ECP Runtime

Reference runtime and CLI for the Evaluation Context Protocol (ECP).

ECP is a vendor-neutral protocol for testing agent outputs, tool calls, and evaluator-visible audit context across frameworks, models, eval platforms, and CI systems.

## Install

```bash
pip install "ecp-runtime==0.3.1"
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

If your manifest includes `llm_judge`, set an API key and optional judge model:

```bash
$env:OPENAI_API_KEY="your_key_here"
$env:ECP_LLM_JUDGE_MODEL="gpt-4o-mini"
```

## Links

- Documentation: https://evaluationcontextprotocol.io/
- Repository: https://github.com/evaluation-context-protocol/ecp
- Issues: https://github.com/evaluation-context-protocol/ecp/issues

