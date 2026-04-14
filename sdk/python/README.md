# ECP Python SDK

This is the SDK for building agents that comply with the Evaluation Context Protocol (ECP).

## Install

```bash
pip install --pre "ecp-sdk==0.2.9b0"
```

The latest stable PyPI release is still `0.2.4`. Use the pinned prerelease above if you want the installed SDK to match the current GitHub `v0.2.9-beta` release line.

For LangChain adaptor support:

```bash
pip install --pre "ecp-sdk[langchain]==0.2.9b0"
```

For CrewAI adaptor support:

```bash
pip install --pre "ecp-sdk[crewai]==0.2.9b0"
```

For LlamaIndex adaptor support:

```bash
pip install --pre "ecp-sdk[llamaindex]==0.2.9b0"
```

For PydanticAI adaptor support:

```bash
pip install --pre "ecp-sdk[pydanticai]==0.2.9b0"
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
