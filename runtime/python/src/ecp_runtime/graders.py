import re
from typing import Any, Dict, List
from .manifest import GraderConfig, StepConfig

def check_text_match(grader: GraderConfig, text: str) -> bool:
    """Handles simple string assertions."""
    if not text:
        return False
        
    val = grader.value
    
    if grader.condition == "contains":
        return val in text
    elif grader.condition == "equals":
        return val == text
    elif grader.condition == "does_not_contain":
        return val not in text
    elif grader.condition == "regex":
        return bool(re.search(grader.pattern, text))
    return False

def evaluate_step(step_config: StepConfig, result_obj: Any) -> List[Dict[str, Any]]:
    """
    Runs all graders for a single step against the agent's result.
    Returns a list of check results.
    """
    check_results = []
    
    for grader in step_config.graders:
        # 1. Select the field to check (Public Output vs Private Thought)
        target_text = ""
        if grader.field == "public_output":
            target_text = result_obj.public_output
        elif grader.field == "private_thought":
            target_text = result_obj.private_thought
            
        # 2. Run the specific grader type
        passed = False
        score = 0.0
        
        if grader.type == "text_match":
            passed = check_text_match(grader, target_text or "")
            score = 1.0 if passed else 0.0
            
        # TODO: Add 'llm_judge' here using OpenAI API
        
        check_results.append({
            "type": grader.type,
            "field": grader.field,
            "passed": passed,
            "score": score
        })
        
    return check_results