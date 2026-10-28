"""
Turn ECP agent steps into DeepEval test cases.

DeepEval grades `LLMTestCase` objects. ECP agents already report the fields DeepEval
needs, from whichever framework they are built in, so this is a direct mapping:

    public_output       -> actual_output
    tool_calls          -> tools_called   (ToolCall name + input_parameters)
    evaluation_context  -> additional_metadata["evaluation_context"]

    from deepeval.metrics import ToolPermissionMetric
    from ecp_runtime.integrations.deepeval import test_cases

    for case in test_cases("python my_agent.py", ["Refund order C300 now"]):
        metric = ToolPermissionMetric(denied_tools=["issue_refund"])
        metric.measure(case)

DeepEval is imported only when this module is used; ECP does not depend on it.

DeepEval's tool metrics treat an empty `tools_called` as "no tools were used". An ECP
agent that has not declared the `tool_calls` capability may simply not report them,
so `to_test_case` refuses that case unless `allow_unreported_tools=True`.
"""

from typing import Any, Dict, Iterable, List, Optional

from ..session import ECPSession, StepOutput


class UnreportedToolCalls(ValueError):
    """The agent did not declare tool_calls, so its empty tool list proves nothing."""


def to_test_case(
    step: StepOutput,
    *,
    expected_output: Optional[str] = None,
    expected_tools: Optional[List[Dict[str, Any]]] = None,
    allow_unreported_tools: bool = False,
    **extra: Any,
):
    from deepeval.test_case import LLMTestCase, ToolCall

    if not step.tool_calls_declared and not allow_unreported_tools:
        raise UnreportedToolCalls(
            "agent did not declare the tool_calls capability; DeepEval would read its empty "
            "tool list as 'no tools used'. Declare the capability, or pass allow_unreported_tools=True."
        )

    def calls(raw):
        return [ToolCall(name=c.get("name"), input_parameters=c.get("arguments") or {}) for c in raw or []]

    metadata = dict(extra.pop("additional_metadata", None) or {})
    metadata.setdefault("evaluation_context", step.evaluation_context)
    metadata.setdefault("usage", step.usage)
    return LLMTestCase(
        input=step.input,
        actual_output=step.public_output or "",
        expected_output=expected_output,
        tools_called=calls(step.tool_calls),
        expected_tools=calls(expected_tools) if expected_tools is not None else None,
        additional_metadata=metadata,
        **extra,
    )


def test_cases(target: str, inputs: Iterable[str], *, fresh_agent_per_input: bool = True, timeout=None, **kwargs):
    """Run each input through an ECP agent and return one DeepEval test case per step.

    With `fresh_agent_per_input` (the default) every input gets its own agent, like
    separate tests; set it False to send the inputs as one multi-turn conversation.
    """
    inputs = list(inputs)
    if fresh_agent_per_input:
        steps = []
        for text in inputs:
            with ECPSession(target, timeout=timeout) as session:
                steps.append(session.step(text))
    else:
        with ECPSession(target, timeout=timeout) as session:
            steps = [session.step(text) for text in inputs]
    return [to_test_case(step, **kwargs) for step in steps]


test_cases.__test__ = False  # not a pytest test, despite the name
