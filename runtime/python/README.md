# ECP Runtime

This is the reference implementation of the Evaluation Context Protocol (ECP) Runtime.
It includes the CLI tool `ecp` for running agent evaluations.

## Install

```bash
pip install "ecp-runtime==0.2.9"
```

The latest stable PyPI release is now `0.2.9` and matches the current GitHub release line.

## Usage

Run an evaluation manifest:

```bash
ecp run --manifest .\examples\langchain_demo\manifest.yaml
```

You can also run via module entrypoint:

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml
```

Manifest `target` values may be either a command for the default stdio transport
or an ECP Streamable HTTP endpoint:

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
