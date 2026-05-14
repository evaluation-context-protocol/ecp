# ECP Python SDK

This is the SDK for building agents that comply with the Evaluation Context Protocol (ECP).

## Install

```bash
pip install "ecp-sdk==0.2.9"
```

The latest stable PyPI release is now `0.2.9`. Use the install command above to install the matching package version.

For LangChain adaptor support:

```bash
pip install "ecp-sdk[langchain]==0.2.9"
```

For CrewAI adaptor support:

```bash
pip install "ecp-sdk[crewai]==0.2.9"
```

For LlamaIndex adaptor support:

```bash
pip install "ecp-sdk[llamaindex]==0.2.9"
```

For PydanticAI adaptor support:

```bash
pip install "ecp-sdk[pydanticai]==0.2.9"
```

## Usage

```python
import ecp

@ecp.agent
class MyAgent:
    ...
```

### Streamable HTTP

Agents can also run as an ECP Streamable HTTP server:

```python
if __name__ == "__main__":
    ecp.serve_http(MyAgent(), host="127.0.0.1", port=8765, path="/ecp")
```

The endpoint accepts JSON-RPC `POST` requests at `/ecp`. It returns JSON for
requests, `202 Accepted` for notifications, and `405 Method Not Allowed` for
`GET` SSE streams until ECP defines server-initiated messages.

## Links

- Documentation: https://evaluationcontextprotocol.io/
- Repository: https://github.com/evaluation-context-protocol/ecp
- Issues: https://github.com/evaluation-context-protocol/ecp/issues
