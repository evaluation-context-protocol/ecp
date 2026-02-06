from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
import yaml

# --- The Grader (Assertion) Schema ---
class GraderConfig(BaseModel):
    type: str 
    field: str = "public_output"
    # For text_match
    condition: Optional[str] = None 
    value: Optional[str] = None
    pattern: Optional[str] = None
    # For llm_judge
    prompt: Optional[str] = None
    assertion: Optional[str] = None
    # For tool_usage
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)

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
    manifest_version: str = "v1"
    name: str
    target: str 
    scenarios: List[ScenarioConfig]

    @classmethod
    def from_yaml(cls, path: str) -> "ECPManifest":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)