from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base class that keeps runtime validation aligned with the JSON schema."""

    model_config = ConfigDict(extra="forbid")


# --- The Grader (Assertion) Schema ---
class GraderConfig(StrictModel):
    type: Literal["text_match", "llm_judge", "tool_usage"]
    field: Literal["public_output", "evaluation_context", "private_thought"] = "public_output"
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
class StepConfig(StrictModel):
    input: str
    constraints: Dict[str, Any] = Field(default_factory=dict)
    graders: List[GraderConfig] = Field(default_factory=list)

class ScenarioConfig(StrictModel):
    name: str = Field(min_length=1)
    steps: List[StepConfig]

# --- The Root Manifest Schema ---
class ECPManifest(StrictModel):
    manifest_version: Literal["v1"]
    name: str = Field(min_length=1)
    target: str = Field(min_length=1)
    scenarios: List[ScenarioConfig]

    @classmethod
    def from_yaml(cls, path: str) -> "ECPManifest":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("Manifest YAML root must be an object")
        return cls(**data)
