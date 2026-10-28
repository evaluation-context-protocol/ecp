import importlib.util
import os
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from .manifest import GraderConfig, StepConfig
except ImportError:
    import os
    import sys
    sys.path.append(os.path.dirname(__file__))
    from manifest import GraderConfig, StepConfig  # type: ignore

# litellm backs the llm_judge grader and ships as the optional `judge` extra.
#
# Catch Exception, not ImportError: a broken or partially-installed litellm can
# raise anything at import time, and the whole runtime should not die because an
# optional grader's dependency is unhappy. `completion` is always bound so the
# attribute exists for tests and introspection either way.
try:
    import litellm
    from litellm import completion  # type: ignore
except Exception as _litellm_import_error:  # noqa: BLE001
    litellm = None  # type: ignore
    completion = None  # type: ignore
    LITELLM_IMPORT_ERROR: Optional[str] = (
        f"{type(_litellm_import_error).__name__}: {_litellm_import_error}"
    )
else:
    LITELLM_IMPORT_ERROR = None

#: True when the llm_judge grader can actually run.
LITELLM_AVAILABLE = litellm is not None


def _litellm_is_installed() -> bool:
    """True when a litellm distribution exists, whether or not it imports.

    The two failures need opposite advice. "Not installed" means install the
    extra; "installed but broken" means installing the extra again - which is what
    a message saying "not installed" tells the user to do - changes nothing.
    """
    try:
        return importlib.util.find_spec("litellm") is not None
    except (ImportError, ValueError):
        return False


def judge_unavailable_message() -> str:
    """Why llm_judge cannot run, with advice matching the actual cause."""
    detail = f" ({LITELLM_IMPORT_ERROR})" if LITELLM_IMPORT_ERROR else ""
    if _litellm_is_installed():
        return (
            "LLM judge unavailable: litellm is installed but failed to import"
            f"{detail}. The installed version is likely incompatible or has missing "
            "dependencies; try `pip install -U litellm`."
        )
    return (
        "LLM judge unavailable: litellm is not installed. "
        f"Install it with `pip install 'ecp-runtime[judge]'`.{detail}"
    )


def _llm_judge_model() -> str:
    return os.environ.get("ECP_LLM_JUDGE_MODEL", "gpt-4o-mini")


def _llm_judge_temperature() -> float:
    raw = os.environ.get("ECP_LLM_JUDGE_TEMPERATURE", "0")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def check_text_match(grader: GraderConfig, text: str) -> Tuple[bool, str]:
    """Handles simple string assertions."""
    if not text:
        return False, "Text was empty"

    val = grader.value
    if grader.condition in {"contains", "equals", "does_not_contain"} and val is None:
        return False, "No 'value' provided for text_match condition"
    if grader.condition == "regex" and not grader.pattern:
        return False, "No 'pattern' provided for regex condition"
    
    if grader.condition == "contains":
        return val in text, f"Expected to contain '{val}'"
    elif grader.condition == "equals":
        return val == text, f"Expected to equal '{val}'"
    elif grader.condition == "does_not_contain":
        return val not in text, f"Expected NOT to contain '{val}'"
    elif grader.condition == "regex":
        return bool(re.search(grader.pattern, text)), f"Regex '{grader.pattern}' failed"
    return False, "Unknown condition"

#: The verdict must be the last thing the judge says.
_VERDICT_AT_END = re.compile(r"RESULT:\s*(PASS|FAIL)\W*$", re.IGNORECASE)


def parse_judge_verdict(content: str) -> Optional[bool]:
    """Read the judge's verdict from the *end* of its response.

    The text under evaluation is untrusted: it is whatever the agent produced, and
    it is placed in the judge's prompt. A judge explaining a failure routinely quotes
    the offending text, so a reply containing the words "RESULT: PASS" ends up quoted
    in a response that concludes "RESULT: FAIL". Searching the whole response for
    "RESULT: PASS" - as this used to - therefore let any agent force a pass just by
    emitting that string, regardless of what the judge decided. Only a verdict at the
    very end counts. Returns None when there is none.
    """
    match = _VERDICT_AT_END.search(content.strip())
    if match is None:
        return None
    return match.group(1).upper() == "PASS"


def check_llm_judge(grader: GraderConfig, text: str) -> Tuple[bool, str, float]:
    """
    Uses an LLM to evaluate the text via LiteLLM.
    Returns: (passed, reasoning, score)
    """
    if not grader.prompt:
        return False, "No prompt provided for llm_judge", 0.0
    if litellm is None:
        return False, judge_unavailable_message(), 0.0
    
    # 1. Construct the Prompt for the Judge
    system_prompt = "You are an impartial AI Judge. You evaluate outputs based on specific criteria."
    user_prompt = f"""
    TASK: Evaluate the following text against the provided criteria.
    
    [TEXT TO EVALUATE]
    {text}
    
    [CRITERIA]
    {grader.prompt}
    
    [ASSERTION]
    Does the text satisfy the criteria? 
    If YES, end your response with "RESULT: PASS".
    If NO, end your response with "RESULT: FAIL".
    Provide a short reasoning before the result.
    """

    # 2. Call the Judge via LiteLLM
    try:
        response = completion(
            model=_llm_judge_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=_llm_judge_temperature(),
            # Current Claude models reject any temperature other than their default
            # ("does not support temperature=0.0. Only temperature=1 is supported"),
            # and a hardcoded 0 made every judge call against them fail. Ask for a
            # deterministic judge, but let litellm drop the parameter where the model
            # will not take it. The cost: such a judge is not deterministic, so judge
            # verdicts should be read over repeated runs.
            drop_params=True,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str):
            return False, "LLM Judge returned non-text content", 0.0
        
        # 3. Parse the Verdict
        verdict = parse_judge_verdict(content)
        if verdict is None:
            # No verdict at the end is a failed grade, never a pass - and the
            # message says the judge's reply was malformed, not that the agent was.
            return (
                False,
                "LLM Judge Error: response did not end with 'RESULT: PASS' or "
                f"'RESULT: FAIL'. Response: {content.strip()[:300]}",
                0.0,
            )
        reasoning = _VERDICT_AT_END.sub("", content.strip()).strip()

        return verdict, reasoning, 1.0 if verdict else 0.0

    except Exception as e:
        return False, f"LLM Judge Error: {str(e)}", 0.0

def evaluate_step(
    step_config: StepConfig,
    result_obj: Any,
    declared_capabilities: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Runs all graders for a single step against the agent's result.

    ``declared_capabilities`` is what the agent reported in ``agent/initialize``.
    It matters for ``not_called`` graders only: a prohibition passes when the
    forbidden call is *absent*, so it is only meaningful if the agent has said it
    reports tool calls at all. ``None`` means the caller does not know, and is
    treated as "declared" - the runner always passes the real value.
    """
    check_results = []
    tool_calls_declared = declared_capabilities is None or "tool_calls" in declared_capabilities
    
    for grader in step_config.graders:
        # Select target field
        target_text = ""
        if grader.field == "public_output":
            target_text = result_obj.public_output
        elif grader.field == "evaluation_context":
            target_text = getattr(result_obj, "evaluation_context", None)
        elif grader.field == "private_thought":
            target_text = getattr(result_obj, "private_thought", None) or getattr(result_obj, "evaluation_context", None)
            
        passed = False
        reasoning = ""
        score = 0.0
        
        # Router
        if grader.type == "text_match":
            passed, reasoning = check_text_match(grader, target_text or "")
            score = 1.0 if passed else 0.0
            
        elif grader.type == "llm_judge":
            passed, reasoning, score = check_llm_judge(grader, target_text or "")
        elif grader.type == "tool_usage":
            passed, reasoning = check_tool_usage(
                grader,
                getattr(result_obj, "tool_calls", None) or [],
                tool_calls_declared=tool_calls_declared,
            )
            score = 1.0 if passed else 0.0
        
        check_results.append({
            "type": grader.type,
            "field": "tool_calls" if grader.type == "tool_usage" else grader.field,
            "passed": passed,
            "score": score,
            "reasoning": reasoning
        })
        
    return check_results

def _call_name(call: Dict[str, Any]) -> Optional[str]:
    return call.get("name") or call.get("tool") or call.get("id")


def _call_arguments(call: Dict[str, Any]) -> Dict[str, Any]:
    args = call.get("arguments") or call.get("args") or {}
    return args if isinstance(args, dict) else {}


def _arguments_match(actual: Dict[str, Any], expected: Dict[str, Any]) -> bool:
    return all(k in actual and actual[k] == v for k, v in expected.items())


def check_tool_not_called(
    grader: GraderConfig,
    tool_calls: List[Dict[str, Any]],
    *,
    tool_calls_declared: bool = True,
) -> Tuple[bool, str]:
    """A prohibition: the named tool must not appear among the reported calls.

    With ``arguments`` set, only calls whose arguments include those pairs are
    forbidden, so ``issue_refund`` with ``amount: "0"`` can be allowed while any
    other refund is not.

    **Absence of evidence is not evidence of absence.** For a presence check a
    silent agent fails safe - nothing was reported, so nothing matched. For a
    prohibition the same silence would *pass*, so an agent or adapter that drops
    tool calls would let a forbidden one through unnoticed. This therefore refuses
    to pass unless the agent has declared the ``tool_calls`` capability.
    """
    name = grader.tool_name
    if not tool_calls_declared:
        return False, (
            f"Cannot verify that '{name}' was not called: the agent does not declare the "
            "'tool_calls' capability, so an empty report would be indistinguishable from "
            "an agent that simply does not report calls. Declare it, for example "
            "@agent(capabilities={'tool_calls': {}}), once you have confirmed the "
            "adapter reports every call."
        )

    expected_args = grader.arguments or {}
    offending = [
        call
        for call in tool_calls
        if _call_name(call) == name and _arguments_match(_call_arguments(call), expected_args)
    ]
    if offending:
        detail = f" with arguments {expected_args}" if expected_args else ""
        return False, (
            f"Forbidden tool '{name}'{detail} was called {len(offending)} time(s): "
            f"{[_call_arguments(c) for c in offending]}"
        )
    seen = [_call_name(c) for c in tool_calls]
    return True, f"'{name}' was not called. Calls seen: {seen}"


def check_tool_usage(
    grader: GraderConfig,
    tool_calls: List[Dict[str, Any]],
    *,
    tool_calls_declared: bool = True,
) -> Tuple[bool, str]:
    """Checks the JSON-RPC result.tool_calls list for a matching tool invocation.

    Expectations come from the manifest:
    - grader.tool_name: required exact match against call name (if provided)
    - grader.arguments: all provided key/value pairs must be present in call arguments
    """
    if grader.condition == "not_called":
        return check_tool_not_called(
            grader, tool_calls if isinstance(tool_calls, list) else [],
            tool_calls_declared=tool_calls_declared,
        )

    if not isinstance(tool_calls, list) or not tool_calls:
        return False, "No tool_calls present. Agent did not report any tool usage."

    expected_name = grader.tool_name
    expected_args = grader.arguments or {}

    def args_match(actual: Dict[str, Any], expected: Dict[str, Any]) -> bool:
        for k, v in expected.items():
            if k not in actual:
                return False
            if actual[k] != v:
                return False
        return True

    for call in tool_calls:
        name = call.get("name") or call.get("tool") or call.get("id")
        args = call.get("arguments") or call.get("args") or {}

        # Name must match if specified
        if expected_name and name != expected_name:
            continue

        # Arguments must include expected pairs
        if args_match(args if isinstance(args, dict) else {}, expected_args):
            return True, f"Found tool call '{name}' with expected arguments"

    available = [call.get("name") or call.get("tool") or call.get("id") for call in tool_calls]
    reason = "No matching tool call"
    if expected_name:
        reason += f" for name='{expected_name}'"
    if expected_args:
        reason += f" and arguments={expected_args}"
    if available:
        reason += f". Calls seen: {available}"
    return False, reason
