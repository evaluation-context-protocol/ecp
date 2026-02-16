# Quickstart

## 1. Create a venv and install from PyPI

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install ecp-runtime "ecp-sdk[langchain]" langchain-openai
```

## 2. Run the demo

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml
```

## 3. Generate an HTML report

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml --report .\report.html
```

## 4. JSON output (for CI)

Print a JSON report to stdout:

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml --json
```

Save a JSON report to a file:

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml --json-out .\report.json
```

## 5. Optional: enable LLM judge

If your manifest uses `llm_judge`, set the API key:

```bash
$env:OPENAI_API_KEY="your_key_here"
```

## Notes

- The runtime launches your agent via the `target` command in the manifest.
- The agent responds over JSON-RPC 2.0 on stdio.
- Use `ECP_RPC_TIMEOUT` to control step timeouts (default 30s).
