# Interop: three evaluators, four agent frameworks, one protocol

Each evaluator used one configuration for all four frameworks; only the agent's `target` changed. Ground truth is the log the agents' tools write themselves.

| Evaluator | Framework | Steps completed | Tool calls received = tool calls made | Real refunds caught by "never call issue_refund" | That verdict correct |
|---|---|---|---|---|---|
| ecp run | crewai | 45/45 | 45/45 | 10/10 | 45/45 |
| ecp run | langchain | 45/45 | 45/45 | 10/10 | 45/45 |
| ecp run | pydanticai | 45/45 | 45/45 | 10/10 | 45/45 |
| ecp run | llamaindex | 45/45 | 45/45 | 10/10 | 45/45 |
| Promptfoo | crewai | 12/12 | 12/12 | 4/4 | 12/12 |
| Promptfoo | langchain | 12/12 | 12/12 | 4/4 | 12/12 |
| Promptfoo | pydanticai | 12/12 | 12/12 | 4/4 | 12/12 |
| Promptfoo | llamaindex | 12/12 | 12/12 | 4/4 | 12/12 |
| DeepEval | crewai | 12/12 | 12/12 | 4/4 | 12/12 |
| DeepEval | langchain | 12/12 | 12/12 | 4/4 | 12/12 |
| DeepEval | pydanticai | 12/12 | 12/12 | 4/4 | 12/12 |
| DeepEval | llamaindex | 12/12 | 12/12 | 4/4 | 12/12 |

**Total:** 276/276 steps completed; tool calls matched ground truth in 276/276; 72/72 real refunds caught; prohibition verdict correct in 276/276.

## Reply judges (for reference; each evaluator uses its own judge)

| Evaluator | Guarded runs: reply passed | Eager runs: reply passed |
|---|---|---|
| ecp run | 120/120 | 20/60 |
| Promptfoo | 24/24 | 8/24 |
| DeepEval | 24/24 | 8/24 |

Errors: 0
