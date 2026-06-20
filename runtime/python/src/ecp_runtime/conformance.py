"""Protocol contract validation shared by runtime execution and conformance checks."""

from typing import Any, Callable, Dict, List, Optional

VALID_STATUSES = {"done", "paused"}


def validate_rpc_response(response: Any, method: str) -> Dict[str, Any]:
    """Validate the JSON-RPC response envelope and return its result."""
    if not isinstance(response, dict):
        raise ValueError(f"{method} response must be a JSON-RPC object")
    if response.get("jsonrpc") != "2.0":
        raise ValueError(f"{method} response must include jsonrpc='2.0'")
    if "id" not in response:
        raise ValueError(f"{method} response must include id")
    if "result" in response and "error" in response:
        raise ValueError(f"{method} response cannot include both result and error")
    if "error" in response:
        error = response["error"]
        if not isinstance(error, dict):
            raise ValueError(f"{method} error must be an object")
        if not isinstance(error.get("code"), int) or not isinstance(error.get("message"), str):
            raise ValueError(f"{method} error must include integer code and string message")
        raise ValueError(f"{method} returned error: {error}")
    if "result" not in response:
        raise ValueError(f"{method} response must include result")
    return response["result"]


def validate_step_result(result: Any) -> Dict[str, Any]:
    """Validate the normative agent/step result contract."""
    if not isinstance(result, dict):
        raise ValueError("agent/step result must be an object")

    status = result.get("status")
    if status not in VALID_STATUSES:
        allowed = ", ".join(sorted(VALID_STATUSES))
        raise ValueError(f"agent/step result status must be one of: {allowed}")

    for field in ("public_output", "evaluation_context", "private_thought", "logs"):
        value = result.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"agent/step result {field} must be a string or null")

    tool_calls = result.get("tool_calls")
    if tool_calls is not None:
        if not isinstance(tool_calls, list):
            raise ValueError("agent/step result tool_calls must be an array or null")
        for index, tool_call in enumerate(tool_calls):
            _validate_tool_call(tool_call, index)

    return result


def validate_initialize_result(result: Any) -> Dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("agent/initialize result must be an object")
    if not isinstance(result.get("name"), str) or not result["name"]:
        raise ValueError("agent/initialize result name must be a non-empty string")
    if not isinstance(result.get("capabilities"), dict):
        raise ValueError("agent/initialize result capabilities must be an object")
    return result


def validate_reset_result(result: Any) -> bool:
    if result is not True:
        raise ValueError("agent/reset result must be true")
    return result


def conformance_check(
    name: str,
    method: str,
    response: Any,
    *,
    result_validator: Optional[Callable[[Any], Any]] = None,
) -> Dict[str, Any]:
    """Return a stable, serializable result for one protocol check."""
    try:
        result = validate_rpc_response(response, method)
        if result_validator:
            result_validator(result)
    except ValueError as exc:
        return {"name": name, "method": method, "passed": False, "message": str(exc)}
    return {"name": name, "method": method, "passed": True, "message": "passed"}


def build_conformance_report(target: str, checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "target": target,
        "conformant": passed == total,
        "passed": passed,
        "failed": total - passed,
        "total": total,
        "checks": checks,
    }


def _validate_tool_call(tool_call: Any, index: Optional[int] = None) -> None:
    label = "tool call" if index is None else f"tool_calls[{index}]"
    if not isinstance(tool_call, dict):
        raise ValueError(f"agent/step result {label} must be an object")
    if not isinstance(tool_call.get("name"), str) or not tool_call["name"]:
        raise ValueError(f"agent/step result {label}.name must be a non-empty string")
    if "arguments" in tool_call and not isinstance(tool_call["arguments"], dict):
        raise ValueError(f"agent/step result {label}.arguments must be an object")
