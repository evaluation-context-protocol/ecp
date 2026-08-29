# Why ECP?

ECP is not trying to replace eval platforms. It standardizes the contract between agents and evaluators so teams can run evals locally, in CI, or inside whichever platform they already use.

## The Gap

Agent teams often need to answer questions that final-output checks miss:

- Did the agent call the required tool?
- Did it use the right arguments?
- Did it follow policy before responding?
- Can we reproduce this in CI?
- Can we move eval results between tools without rewriting the agent?

Tracing and hosted eval platforms help, but the data model is usually tied to that platform. ECP makes the agent evaluation surface portable.

## ECP Compared

| Tooling Category | What It Is Good At | Where ECP Fits |
| --- | --- | --- |
| Unit tests | deterministic code checks | ECP adds agent/tool/evaluation surfaces |
| LLM judges | semantic output grading | ECP makes judge inputs and results repeatable |
| Trace platforms | observability and debugging | ECP provides a small portable eval contract |
| Eval platforms | datasets, dashboards, experiments | ECP can feed or interoperate with platforms |

## The MCP Analogy

MCP standardizes how agents connect to tools.

ECP standardizes how agents expose evaluation results:

- `public_output`
- `evaluation_context`
- `tool_calls`
- manifest scenarios
- grader results
- portable reports

## The Enterprise Angle

Enterprise teams care about auditability, regression testing, policy compliance, data boundaries, vendor flexibility, and CI workflows. ECP is designed to be boring infrastructure: a small contract that can sit under many tools instead of forcing every team into one hosted workflow.
