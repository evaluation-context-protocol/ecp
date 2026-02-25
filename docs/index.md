# Evaluation Context Protocol (ECP)

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [README](https://github.com/evaluation-context-protocol/ecp/blob/main/README.md)

ECP is a lightweight protocol and reference runtime for evaluating agents with public output, private reasoning, and tool usage.

It gives you a standard way to run deterministic evaluations without changing your production agent code.

## Why ECP exists

Most agent evaluations only check the final answer. That is not enough for safety or reliability.

Common gaps:

- Did the agent use the right tool or hallucinate data?
- Did it follow policy internally before responding?
- Did it reason correctly even if the final answer looks right?

ECP solves this by separating **public output** (what users see) from **private reasoning** and **tool calls** (what evaluators need to verify). The runtime can then grade each aspect explicitly.

## What you get

- A simple JSON-RPC protocol over stdio
- A reference runtime to execute manifests and graders
- Optional HTML report output for sharing results
- A Python SDK to wrap agents quickly
- Minimal examples for LangChain, LlamaIndex, and CrewAI

## Framework Adaptors

- LangChain: `ecp.adaptors.langchain.ECPLangChainAdapter`
- LlamaIndex: `ecp.adaptors.llama_index.ECPLlamaIndexAdapter`
- CrewAI: `ecp.adaptors.crewai.ECPCrewAIAdapter`

See **Examples** for full agent + manifest snippets.

## What is in this repo

- Python SDK: `sdk/python/src/ecp`
- Runtime CLI: `runtime/python/src/ecp_runtime`
- Examples: `examples/langchain_demo`, `examples/llamaindex_demo`, `examples/crewai_demo`
- Protocol spec: `spec/protocol.md`

Go to **Quickstart** to run the demos, **Examples** for full manifests, or **Specification** to implement the protocol in another language.
