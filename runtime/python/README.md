# ECP Runtime

This is the reference implementation of the Evaluation Context Protocol (ECP) Runtime.
It includes the CLI tool `ecp` for running agent evaluations.

## Install

```bash
pip install ecp-runtime
```

## Usage

Run an evaluation manifest:

```bash
ecp run --manifest .\examples\langchain_demo\manifest.yaml
```

You can also run via module entrypoint:

```bash
python -m ecp_runtime.cli run --manifest .\examples\langchain_demo\manifest.yaml
```

## Links

- Documentation: https://evaluation-context-protocol.github.io/ecp/
- Repository: https://github.com/evaluation-context-protocol/ecp
- Issues: https://github.com/evaluation-context-protocol/ecp/issues
