# Quickstart

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Docs Home](https://evaluationcontextprotocol.io/)

## 1. Create a venv and install the current PyPI prerelease

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --pre "ecp-runtime==0.2.9b0" "ecp-sdk[langchain]==0.2.9b0" langchain-openai
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
pip install --pre "ecp-sdk[crewai]==0.2.9b0" crewai
```

Run CrewAI manifest:

```bash
python -m ecp_runtime.cli run --manifest .\examples\crewai_demo\manifest.yaml
```

## 6. Run the PydanticAI demo

Install PydanticAI support:

```bash
pip install --pre "ecp-sdk[pydanticai]==0.2.9b0" pydantic-ai
```

Run PydanticAI manifest:

```bash
python -m ecp_runtime.cli run --manifest .\examples\pydantic_ai_demo\manifest.yaml
```

## 7. Run the LlamaIndex demo

Install LlamaIndex support:

```bash
pip install "ecp-sdk[llamaindex]" llama-index llama-index-llms-openai llama-index-tools-yahoo-finance
```

Run LlamaIndex manifest:

```bash
python -m ecp_runtime.cli run --manifest .\examples\llamaindex_demo\manifest.yaml
```

## 8. Optional: enable LLM judge

If your manifest uses `llm_judge`, set the API key:

```bash
$env:OPENAI_API_KEY="your_key_here"
$env:ECP_LLM_JUDGE_MODEL="gpt-4o-mini"
$env:ECP_LLM_JUDGE_TEMPERATURE="0"
```

## Notes

- The latest stable packages on PyPI are still `0.2.4`. This docs site currently matches the `0.2.9-beta` release line, so use the prerelease install command above if you want the published packages to match the repo and GitHub release.
- The runtime launches your agent via the `target` command in the manifest.
- The agent responds over JSON-RPC 2.0 on stdio.
- Use `ECP_RPC_TIMEOUT` to control step timeouts (default 30s).
