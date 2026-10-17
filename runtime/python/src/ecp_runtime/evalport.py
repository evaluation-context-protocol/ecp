"""
ecp_runtime.evalport
====================
Load an EvalPort ``EvalSuite`` as ECP scenarios.

`EvalPort <https://github.com/adhabnr-ux/evalport>`_ is a JSON interchange
format for portable eval *datasets* - suites of test cases and grader
definitions. Its spec explicitly declines to define a runner or a trace format,
which is exactly ECP's territory. The two sit at adjacent layers: EvalPort says
*what* to test, ECP runs it against a live agent.

This module is the inbound direction. It lets a manifest point at an EvalPort
suite instead of hand-written steps::

    scenarios:
      - name: "GSM8K"
        dataset:
          type: "evalport"
          source: "suites/gsm8k.json"

**Unsupported graders are a hard error, never a silent drop.** A suite using
``code`` or ``semantic_similarity`` would otherwise load, run, and report a
healthy pass rate having never applied the check that mattered - the same class
of failure as counting a timed-out step as a pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: EvalPort grader types this runtime can execute, mapped onto ECP graders.
SUPPORTED_GRADER_TYPES = frozenset({"exact_match", "contains", "regex", "llm_judge"})

#: Well-known EvalPort types ECP cannot run yet, named so the error is specific.
KNOWN_UNSUPPORTED_GRADER_TYPES = frozenset(
    {"semantic_similarity", "json_schema", "json_path", "code", "human", "model_graded", "custom"}
)

#: Regex flags expressible as an inline Python group, so they map losslessly.
_INLINE_REGEX_FLAGS = frozenset("imsxa")


class EvalPortError(ValueError):
    """An EvalPort suite could not be mapped onto ECP scenarios."""


def load_suite(path: str | Path) -> Dict[str, Any]:
    """Read and shape-check an EvalPort suite file."""
    suite_path = Path(path)
    try:
        # EvalPort suites are UTF-8; benchmark text routinely carries typographic
        # punctuation, which the platform default codec mangles on Windows.
        raw = suite_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvalPortError(f"EvalPort suite not readable: {suite_path}: {exc}") from exc

    try:
        suite = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvalPortError(f"EvalPort suite is not valid JSON: {suite_path}: {exc}") from exc

    if not isinstance(suite, dict):
        raise EvalPortError(f"EvalPort suite root must be an object: {suite_path}")
    for field in ("version", "id"):
        if not isinstance(suite.get(field), str) or not suite[field]:
            raise EvalPortError(f"EvalPort suite missing required '{field}': {suite_path}")

    if "test_cases_file" in suite and "test_cases" not in suite:
        raise EvalPortError(
            "EvalPort suites using 'test_cases_file' (external JSONL) are not supported yet; "
            f"inline 'test_cases' are required: {suite_path}"
        )

    test_cases = suite.get("test_cases")
    if not isinstance(test_cases, list) or not test_cases:
        raise EvalPortError(f"EvalPort suite has no test_cases: {suite_path}")

    return suite


def suite_to_steps(suite: Dict[str, Any], *, source: str = "<suite>") -> List[Dict[str, Any]]:
    """Map a suite onto ECP step dictionaries, ready for ``StepConfig``.

    Returns plain dicts rather than models so this module stays importable
    without a circular dependency on ``manifest``.
    """
    shared = _index_shared_graders(suite, source=source)

    steps: List[Dict[str, Any]] = []
    unsupported: List[str] = []

    for index, case in enumerate(suite["test_cases"]):
        if not isinstance(case, dict):
            raise EvalPortError(f"{source}: test_cases[{index}] must be an object")

        case_id = case.get("id") or f"case_{index}"
        turns = _case_turns(case, case_id=case_id, source=source)

        try:
            graders = _case_graders(case, shared, case_id=case_id, source=source)
        except _UnsupportedGrader as exc:
            unsupported.append(f"{case_id}: {exc}")
            continue

        # EvalPort grades a test case's final output. For a multi-turn input the
        # earlier turns are setup, so graders attach to the last step only.
        for turn_index, turn in enumerate(turns):
            is_last = turn_index == len(turns) - 1
            steps.append({"input": turn, "graders": graders if is_last else []})

    if unsupported:
        shown = "\n  ".join(unsupported[:10])
        more = f"\n  ... and {len(unsupported) - 10} more" if len(unsupported) > 10 else ""
        raise EvalPortError(
            f"{source}: {len(unsupported)} test case(s) use graders ECP cannot run.\n"
            f"  {shown}{more}\n"
            f"ECP currently maps: {', '.join(sorted(SUPPORTED_GRADER_TYPES))}. "
            "Running the suite without them would report a pass rate for checks that never ran."
        )

    if not steps:
        raise EvalPortError(f"{source}: produced no runnable steps")

    return steps


# --- internals -------------------------------------------------------------


class _UnsupportedGrader(Exception):
    """Raised per test case, collected so the error names every offender."""


def _index_shared_graders(suite: Dict[str, Any], *, source: str) -> Dict[str, Dict[str, Any]]:
    shared: Dict[str, Dict[str, Any]] = {}
    for index, grader in enumerate(suite.get("graders") or []):
        if not isinstance(grader, dict):
            raise EvalPortError(f"{source}: graders[{index}] must be an object")
        grader_id = grader.get("id")
        if not isinstance(grader_id, str) or not grader_id:
            raise EvalPortError(f"{source}: graders[{index}] missing 'id'")
        if grader_id in shared:
            raise EvalPortError(f"{source}: duplicate grader id {grader_id!r}")
        shared[grader_id] = grader
    return shared


def _case_turns(case: Dict[str, Any], *, case_id: str, source: str) -> List[str]:
    raw = case.get("input")
    if isinstance(raw, str):
        turns = [raw]
    elif isinstance(raw, list):
        turns = [t for t in raw if isinstance(t, str)]
        if len(turns) != len(raw):
            raise EvalPortError(f"{source}: {case_id} multi-turn input must be all strings")
    else:
        raise EvalPortError(f"{source}: {case_id} 'input' must be a string or array of strings")

    if not turns:
        raise EvalPortError(f"{source}: {case_id} has an empty input")
    return turns


def _case_graders(
    case: Dict[str, Any],
    shared: Dict[str, Dict[str, Any]],
    *,
    case_id: str,
    source: str,
) -> List[Dict[str, Any]]:
    mapped: List[Dict[str, Any]] = []

    for ref in case.get("graders") or []:
        if isinstance(ref, str):
            grader = shared.get(ref)
            if grader is None:
                raise EvalPortError(f"{source}: {case_id} references unknown grader id {ref!r}")
        elif isinstance(ref, dict):
            grader = ref
        else:
            raise EvalPortError(f"{source}: {case_id} grader entry must be an id or object")

        mapped.append(_map_grader(grader, case=case, case_id=case_id, source=source))

    # EvalPort's agent profile asserts which tools should have been called.
    # ECP's tool_usage is strictly more precise, so this maps cleanly.
    for tool in case.get("expected_tools") or []:
        if not isinstance(tool, str) or not tool:
            raise EvalPortError(f"{source}: {case_id} expected_tools entries must be strings")
        mapped.append({"type": "tool_usage", "tool_name": tool, "arguments": {}})

    if not mapped:
        raise EvalPortError(f"{source}: {case_id} produced no graders")
    return mapped


def _map_grader(
    grader: Dict[str, Any], *, case: Dict[str, Any], case_id: str, source: str
) -> Dict[str, Any]:
    grader_type = grader.get("type")
    if not isinstance(grader_type, str) or not grader_type:
        raise EvalPortError(f"{source}: {case_id} grader missing 'type'")

    if grader_type not in SUPPORTED_GRADER_TYPES:
        known = " (a well-known EvalPort type)" if grader_type in KNOWN_UNSUPPORTED_GRADER_TYPES else ""
        raise _UnsupportedGrader(f"grader type {grader_type!r}{known}")

    params = grader.get("params") or {}
    if not isinstance(params, dict):
        raise EvalPortError(f"{source}: {case_id} grader 'params' must be an object")

    ignore_case = bool(params.get("ignore_case", False))
    strip = bool(params.get("strip", False))

    if grader_type == "exact_match":
        expected = case.get("expected_output")
        if not isinstance(expected, str):
            raise EvalPortError(
                f"{source}: {case_id} uses exact_match but has no string 'expected_output'"
            )
        return {
            "type": "text_match",
            "field": "public_output",
            "condition": "equals",
            "value": expected,
            "ignore_case": ignore_case,
            "strip": strip,
        }

    if grader_type == "contains":
        substring = params.get("substring")
        if not isinstance(substring, str) or not substring:
            raise EvalPortError(f"{source}: {case_id} contains grader needs params.substring")
        return {
            "type": "text_match",
            "field": "public_output",
            "condition": "contains",
            "value": substring,
            "ignore_case": ignore_case,
            "strip": strip,
        }

    if grader_type == "regex":
        pattern, flags = _regex_pattern(params, case_id=case_id, source=source)
        return {
            "type": "text_match",
            "field": "public_output",
            "condition": "regex",
            "pattern": pattern,
            # Flags are folded into the pattern, so the options stay off here.
            "ignore_case": False,
            "strip": strip,
        }

    # llm_judge
    prompt = params.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise EvalPortError(f"{source}: {case_id} llm_judge grader needs params.prompt")
    return {"type": "llm_judge", "field": "public_output", "prompt": prompt}


def _regex_pattern(
    params: Dict[str, Any], *, case_id: str, source: str
) -> Tuple[str, Optional[str]]:
    pattern = params.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        raise EvalPortError(f"{source}: {case_id} regex grader needs params.pattern")

    flags = params.get("flags")
    if flags in (None, ""):
        return pattern, None
    if not isinstance(flags, str):
        raise EvalPortError(f"{source}: {case_id} regex 'flags' must be a string")

    unknown = sorted(set(flags) - _INLINE_REGEX_FLAGS)
    if unknown:
        raise EvalPortError(
            f"{source}: {case_id} regex flags {''.join(unknown)!r} cannot be mapped; "
            f"supported inline flags are {''.join(sorted(_INLINE_REGEX_FLAGS))}"
        )
    # ECP's regex condition calls re.search without a flags argument, so express
    # them as an inline group instead of dropping them.
    return f"(?{flags}){pattern}", flags


def describe_unmapped_fields(suite: Dict[str, Any]) -> List[str]:
    """Report suite features that load fine but carry no ECP meaning.

    These are not errors - they do not change pass/fail - but a user comparing
    an ECP run against another EvalPort runner should know they were ignored.
    """
    notes: List[str] = []
    cases = suite.get("test_cases") or []

    if any(isinstance(c, dict) and c.get("weight") is not None for c in cases):
        notes.append("test case 'weight' ignored: ECP does not weight grader aggregation")
    if any(isinstance(c, dict) and c.get("timeout_ms") is not None for c in cases):
        notes.append("test case 'timeout_ms' ignored: ECP bounds runs with --timeout/--max-duration")
    if any(isinstance(c, dict) and c.get("provider") for c in cases) or (
        suite.get("config") or {}
    ).get("provider"):
        notes.append("'provider' ignored: the ECP manifest 'target' selects the system under test")
    if any(isinstance(c, dict) and (c.get("context") or c.get("retrieval_context")) for c in cases):
        notes.append("'context'/'retrieval_context' ignored: ECP passes only the step input")

    # A pinned judge model is a comparability guarantee in EvalPort. ECP reads
    # the judge model from the environment, so the pin cannot be honoured.
    for grader in suite.get("graders") or []:
        if isinstance(grader, dict) and grader.get("type") == "llm_judge":
            model = (grader.get("params") or {}).get("model")
            if model:
                notes.append(
                    f"llm_judge pins model {model!r}, which ECP cannot honour; "
                    "set ECP_LLM_JUDGE_MODEL to match before comparing scores"
                )
            break

    return notes
