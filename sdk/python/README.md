# ECP Python SDK

This is the SDK for building agents that comply with the Evaluation Context Protocol (ECP).

## Install

```bash
pip install ecp-sdk
```

For LangChain adaptor support:

```bash
pip install "ecp-sdk[langchain]"
```

For LlamaIndex adaptor support:

```bash
pip install "ecp-sdk[llamaindex]"
```

## Usage

```python
import ecp

@ecp.agent
class MyAgent:
    ...
```

## Links

- Documentation: https://evaluation-context-protocol.github.io/ecp/
- Repository: https://github.com/evaluation-context-protocol/ecp
- Issues: https://github.com/evaluation-context-protocol/ecp/issues
