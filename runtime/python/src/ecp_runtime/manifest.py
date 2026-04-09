from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator
import yaml

# --- The Grader (Assertion) Schema ---
class GraderConfig(BaseModel):
    type: Literal["text_match", "llm_judge", "tool_usage"]
    field: Literal["public_output", "private_thought"] = "public_output"
    # For text_match
    condition: Optional[Literal["contains", "equals", "does_not_contain", "regex"]] = None
    value: Optional[str] = None
    pattern: Optional[str] = None
    # For llm_judge
    prompt: Optional[str] = None
    assertion: Optional[str] = None
    # For tool_usage
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_by_type(self) -> "GraderConfig":
        if self.type == "text_match":
            if not self.condition:
                raise ValueError("text_match grader requires 'condition'")
            if self.condition == "regex":
                if not self.pattern:
                    raise ValueError("text_match with condition=regex requires 'pattern'")
            elif self.value is None:
                raise ValueError(f"text_match with condition={self.condition} requires 'value'")

        elif self.type == "llm_judge":
            if not self.prompt or not self.prompt.strip():
                raise ValueError("llm_judge grader requires non-empty 'prompt'")

        elif self.type == "tool_usage":
            if not isinstance(self.arguments, dict):
                raise ValueError("tool_usage grader 'arguments' must be an object/dictionary")

        return self

# --- The Step (Scenario) Schema ---
class StepConfig(BaseModel):
    input: str
    constraints: Dict[str, Any] = Field(default_factory=dict)
    graders: List[GraderConfig] = Field(default_factory=list)

class ScenarioConfig(BaseModel):
    name: str
    steps: List[StepConfig]

# --- The Root Manifest Schema ---
class ECPManifest(BaseModel):
    manifest_version: Literal["v1"] = "v1"
    name: str
    target: str
    scenarios: List[ScenarioConfig]

    @classmethod
    def from_yaml(cls, path: str) -> "ECPManifest":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("Manifest YAML root must be an object")
        return cls(**data)
