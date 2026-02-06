import re
import os
from typing import Any, Dict, List, Tuple
from .manifest import GraderConfig, StepConfig

# Try importing OpenAI, but don't crash if it's missing (unless used)
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

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

def check_llm_judge(grader: GraderConfig, text: str) -> Tuple[bool, str, float]:
    """
    Uses an LLM to evaluate the text.
    Returns: (passed, reasoning, score)
    """
    if not grader.prompt:
        return False, "No prompt provided for llm_judge", 0.0
    if OpenAI is None:
        return False, "OpenAI library not installed. Run 'pip install openai'", 0.0
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return False, "OPENAI_API_KEY not set in environment", 0.0

    client = OpenAI(api_key=api_key)
    
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

    # 2. Call the Judge (using a cheap, smart model)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Fast, cheap, smart enough for grading
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0
        )
        content = response.choices[0].message.content
        
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
        elif grader.field == "private_thought":
            target_text = result_obj.private_thought
            
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
            "field": grader.field,
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
