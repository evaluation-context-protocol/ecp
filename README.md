# Evaluation Context Protocol (ECP)

ECP is a standardized interface for orchestrating, auditing, and enforcing authority limits in AI Agent evaluations. It moves evaluation from "brittle Python scripts" to a deterministic infrastructure protocol.

## 🚨 The Problem
Current agent evaluation is broken:

- **Implicit State**: Agents carry memory pollution between test runs.

- **Judge Overreach**: "LLM-as-a-Judge" evaluators see the entire context window, biasing their grading with internal reasoning traces they shouldn't see.

- **Fragile Scaffolding**: Every developer writes their own custom for loop to run an agent.

## ⚡ The Solution: ECP
ECP is **not** a library of metrics. It is a **Protocol** (similar to LSP or MCP) that defines how an **Evaluation Runtime** talks to an **Agent**.

By standardizing the communication layer, ECP guarantees:

- **Strict Authority Limits**: The Runtime acts as a firewall. It can physically prevent an Evaluator (e.g., GPT-4 Judge) from seeing the Agent's "Private Thoughts," ensuring the grade is based only on public behavior.

- **Deterministic Lifecycle**: Enforced `reset()`, `step()`, and `snapshot()` methods ensure a clean room for every test case.

- **Declarative Manifests**: Tests are defined in YAML, declaring exactly who (Actors) has what authority.
