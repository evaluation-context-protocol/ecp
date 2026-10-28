"""
Generate one manifest per framework from the example's manifest.

"The same manifest" is the claim under test, so it is enforced rather than promised:
each generated manifest is the example's manifest with only the `target:` line
replaced, and this script asserts that every other byte is identical across all of
them before writing anything.

Each framework runs in its own virtual environment (frameworks rarely agree on
dependency versions), so each target names that environment's interpreter. Those
paths are machine-specific and are generated at run time into a git-ignored
directory. Override a location with ECP_PORTABILITY_VENV_<NAME>.
"""

import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TEMPLATE = REPO / "examples" / "crewai_claude_crew" / "manifest.yaml"
OUT = HERE / "manifests"

FRAMEWORKS = ("crewai", "langchain", "pydanticai", "llamaindex")
# CrewAI reuses the venv built for the example crew; the rest are built for this study.
DEFAULT_VENV = {
    "crewai": Path.home() / "ecpcrew-venv",
    "langchain": Path.home() / "ecpfw-langchain",
    "pydanticai": Path.home() / "ecpfw-pydanticai",
    "llamaindex": Path.home() / "ecpfw-llamaindex",
}


def interpreter(framework: str) -> Path:
    venv = Path(os.environ.get(f"ECP_PORTABILITY_VENV_{framework.upper()}", DEFAULT_VENV[framework]))
    exe = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not exe.exists():
        raise SystemExit(f"no interpreter for {framework} at {exe}")
    return exe


def target_for(framework: str) -> str:
    agent = (HERE / "agents" / f"agent_{framework}.py").relative_to(REPO).as_posix()
    return f'"{interpreter(framework).as_posix()} {agent}"'


def build(frameworks=FRAMEWORKS) -> dict:
    text = TEMPLATE.read_text(encoding="utf-8")
    pattern = re.compile(r'^target:.*$', re.MULTILINE)
    assert len(pattern.findall(text)) == 1, "expected exactly one target: line in the template"

    manifests = {fw: pattern.sub(f"target: {target_for(fw)}", text) for fw in frameworks}

    # The claim being tested: nothing but the target differs between frameworks.
    neutral = {fw: pattern.sub("target: <T>", m) for fw, m in manifests.items()}
    assert len(set(neutral.values())) == 1, "manifests differ in more than their target"

    OUT.mkdir(parents=True, exist_ok=True)
    for fw, body in manifests.items():
        (OUT / f"manifest_{fw}.yaml").write_text(body, encoding="utf-8")
    return manifests


if __name__ == "__main__":
    chosen = tuple(sys.argv[1:]) or FRAMEWORKS
    built = build(chosen)
    print(f"wrote {len(built)} manifests, identical except for target:")
    for fw in built:
        line = next(ln for ln in built[fw].splitlines() if ln.startswith("target:"))
        print(f"  {fw:11} {line}")
