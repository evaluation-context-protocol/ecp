# Examples

[View on GitHub](https://github.com/evaluation-context-protocol/ecp) | [Docs Home](https://evaluation-context-protocol.github.io/ecp/)

## LangChain Example

Agent file: `examples/langchain_demo/agent.py`

### LangChain Manifest (Full Scenarios)

```yaml
manifest_version: "v1"
name: "LangChain Math Check"
target: "python agent.py"

scenarios:
  - name: "Ratio Word Problem"
    steps:
      - input: "Katy makes coffee using teaspoons of sugar and cups of water in the ratio of 7:13. If she used a total of 120 teaspoons of sugar and cups of water, calculate the number of teaspoonfuls of sugar she used."
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "42"

          - type: llm_judge
            field: public_output
            prompt: "Does the response state the correct final number and clearly indicate it refers to the amount of sugar?"

          - type: tool_usage
            tool_name: "calculator"
            arguments: {}

  - name: "Weekly Letters"
    steps:
      - input: "James writes a 3-page letter to 2 different friends twice a week. How many pages does he write a year?"
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "624"

          - type: llm_judge
            field: public_output
            prompt: "Does the response state the correct final number and clearly indicate it refers to pages written per year?"

          - type: tool_usage
            tool_name: "calculator"
            arguments: {}
```

## LlamaIndex Example

Agent file: `examples/llamaindex_demo/agent.py`

```python
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI
from llama_index.tools.yahoo_finance import YahooFinanceToolSpec

from ecp import serve
from ecp.adaptors.llama_index import ECPLlamaIndexAdapter


def multiply(a: float, b: float) -> float:
    return a * b


def add(a: float, b: float) -> float:
    return a + b


finance_tools = YahooFinanceToolSpec().to_tool_list()
finance_tools.extend([multiply, add])

workflow = FunctionAgent(
    name="Agent",
    description="Useful for performing financial operations.",
    llm=OpenAI(model="gpt-4o-mini"),
    tools=[multiply, add],
    system_prompt="You are a helpful assistant.",
)

ecp_agent = ECPLlamaIndexAdapter(workflow, name="FinanceBot")

if __name__ == "__main__":
    serve(ecp_agent)
```

### LlamaIndex Manifest

```yaml
manifest_version: "v1"
name: "LlamaIndex Capability Check"
target: "python agent.py"

scenarios:
  - name: "Ratio Word Problem"
    steps:
      - input: "Katy makes coffee using teaspoons of sugar and cups of water in the ratio of 7:13. If she used a total of 120 teaspoons of sugar and cups of water, calculate the number of teaspoonfuls of sugar she used."
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "42"

          - type: llm_judge
            field: public_output
            prompt: "Does the response state the correct final number and clearly indicate it refers to the amount of sugar?"

  - name: "Weekly Letters"
    steps:
      - input: "James writes a 3-page letter to 2 different friends twice a week. How many pages does he write a year?"
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "312"

          - type: llm_judge
            field: public_output
            prompt: "Does the response state the correct final number and clearly indicate it refers to pages written per year?"
```
