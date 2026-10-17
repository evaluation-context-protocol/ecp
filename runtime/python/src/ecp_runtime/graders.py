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


def _llm_judge_model() -> str:
    return os.environ.get("ECP_LLM_JUDGE_MODEL", "gpt-4o-mini")


def _llm_judge_temperature() -> float:
    raw = os.environ.get("ECP_LLM_JUDGE_TEMPERATURE", "0")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _apply_text_options(grader: GraderConfig, *values: Optional[str]) -> List[str]:
    """Apply a grader's comparison options to every operand consistently.

    Both sides must be normalized the same way, otherwise `ignore_case` would
    compare a lowered haystack against an un-lowered needle and never match.
    """
    out = []
    for value in values:
        value = "" if value is None else value
        if grader.strip:
            value = value.strip()
        if grader.ignore_case:
            value = value.casefold()
        out.append(value)
    return out


def check_text_match(grader: GraderConfig, text: str) -> Tuple[bool, str]:
    """Handles simple string assertions."""
    if not text:
        return False, "Text was empty"

    val = grader.value
    if grader.condition in {"contains", "equals", "does_not_contain"} and val is None:
        return False, "No 'value' provided for text_match condition"
    if grader.condition == "regex" and not grader.pattern:
        return False, "No 'pattern' provided for regex condition"
    
    if grader.condition in {"contains", "equals", "does_not_contain"}:
        needle, haystack = _apply_text_options(grader, val, text)
        if grader.condition == "contains":
            return needle in haystack, f"Expected to contain '{val}'"
        if grader.condition == "equals":
            return needle == haystack, f"Expected to equal '{val}'"
        return needle not in haystack, f"Expected NOT to contain '{val}'"
    elif grader.condition == "regex":
        return bool(re.search(grader.pattern, text)), f"Regex '{grader.pattern}' failed"
    return False, "Unknown condition"

def check_llm_judge(grader: GraderConfig, text: str) -> Tuple[bool, str, float]:
    """
    Uses an LLM to evaluate the text via LiteLLM.
    Returns: (passed, reasoning, score)
    """
    if not grader.prompt:
        return False, "No prompt provided for llm_judge", 0.0
    if litellm is None:
        detail = ""
        if LITELLM_IMPORT_ERROR:
            detail = f" (import failed: {LITELLM_IMPORT_ERROR})"
        return (
            False,
            "LLM judge unavailable: litellm is not installed. "
            f"Install it with `pip install 'ecp-runtime[judge]'`.{detail}",
            0.0,
        )
    
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
            temperature=_llm_judge_temperature()
        )
        content = response.choices[0].message.content
        if not isinstance(content, str):
            return False, "LLM Judge returned non-text content", 0.0
        
        # 3. Parse the Verdict
        passed = "RESULT: PASS" in content
        reasoning = content.replace("RESULT: PASS", "").replace("RESULT: FAIL", "").strip()
        
        return passed, reasoning, 1.0 if passed else 0.0

    except Exception as e:
        return False, f"LLM Judge Error: {str(e)}", 0.0

def evaluate_step(step_config: StepConfig, result_obj: Any) -> List[Dict[str, Any]]:
    """
    Runs all graders for a single step against the agent's result.
    """
    check_results = []
    
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
            passed, reasoning = check_tool_usage(grader, getattr(result_obj, "tool_calls", None) or [])
            score = 1.0 if passed else 0.0
        
        check_results.append({
            "type": grader.type,
            "field": "tool_calls" if grader.type == "tool_usage" else grader.field,
            "passed": passed,
            "score": score,
            "reasoning": reasoning
        })
        
    return check_results

def check_tool_usage(grader: GraderConfig, tool_calls: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """Checks the JSON-RPC result.tool_calls list for a matching tool invocation.

    Expectations come from the manifest:
    - grader.tool_name: required exact match against call name (if provided)
    - grader.arguments: all provided key/value pairs must be present in call arguments
    """
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
