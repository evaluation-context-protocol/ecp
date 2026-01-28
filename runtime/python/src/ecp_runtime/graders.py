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
        
        check_results.append({
            "type": grader.type,
            "field": grader.field,
            "passed": passed,
            "score": score,
            "reasoning": reasoning
        })
        
    return check_results