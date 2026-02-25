# Quickstart

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Docs Home](https://evaluation-context-protocol.github.io/ecp/)

## 1. Create a venv and install from PyPI

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install ecp-runtime "ecp-sdk[langchain]" langchain-openai
```

## 2. Run the LangChain demo

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

## 5. Run the CrewAI demo

Install CrewAI support:

```bash
pip install "ecp-sdk[crewai]" crewai
```

Run CrewAI manifest:

```bash
python -m ecp_runtime.cli run --manifest .\examples\crewai_demo\manifest.yaml
```

## 6. Optional: enable LLM judge

If your manifest uses `llm_judge`, set the API key:

```bash
$env:OPENAI_API_KEY="your_key_here"
```

## Notes

- The runtime launches your agent via the `target` command in the manifest.
- The agent responds over JSON-RPC 2.0 on stdio.
- Use `ECP_RPC_TIMEOUT` to control step timeouts (default 30s).
