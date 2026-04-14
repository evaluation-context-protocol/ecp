# ECP Runtime

This is the reference implementation of the Evaluation Context Protocol (ECP) Runtime.
It includes the CLI tool `ecp` for running agent evaluations.

## Install

```bash
pip install --pre "ecp-runtime==0.2.9b0"
```

The latest stable PyPI release is still `0.2.4`. Use the pinned prerelease above if you want the installed runtime to match the current GitHub `v0.2.9-beta` release line.

## Usage

Run an evaluation manifest:

```bash
ecp run --manifest .\examples\langchain_demo\manifest.yaml
```

You can also run via module entrypoint:

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml
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
