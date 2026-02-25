from typing import Any, Callable, Dict, List, Optional
import json

from ecp import Result, agent, on_step


class ECPCrewAIAdapter:
    """
    Wraps a CrewAI Crew and exposes it as an ECP-compatible agent.
    """

    def __init__(
        self,
        crew: Any,
        name: str = "CrewAIAgent",
        input_mapper: Optional[Callable[[str], Any]] = None,
        run_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self.crew = crew
        self.name = name
        self.input_mapper = input_mapper or (lambda text: {"input": text})
        self.run_kwargs = run_kwargs or {}

        self.captured_thoughts: List[str] = []
        self.captured_tool_calls: List[Dict[str, Any]] = []

        self._ecp_meta = {"name": name}

    def step(self, input_text: str) -> Result:
        self.captured_thoughts = []
        self.captured_tool_calls = []

        kickoff_kwargs = self._build_kickoff_kwargs(input_text)
        response = self.crew.kickoff(**kickoff_kwargs)

        self._capture_from_response(response)
        final_text = self._extract_final_text(response)

        return Result(
            status="done",
            public_output=final_text,
            private_thought="\n".join(self.captured_thoughts) if self.captured_thoughts else None,
            tool_calls=self.captured_tool_calls or None,
        )

    def _build_kickoff_kwargs(self, input_text: str) -> Dict[str, Any]:
        mapped = self.input_mapper(input_text)
        kickoff_kwargs = dict(self.run_kwargs)

        base_inputs = kickoff_kwargs.pop("inputs", {})
        if not isinstance(base_inputs, dict):
            base_inputs = {}

        if isinstance(mapped, dict):
            inputs = {**base_inputs, **mapped}
        else:
            inputs = {**base_inputs, "input": mapped}

        kickoff_kwargs["inputs"] = inputs
        return kickoff_kwargs

    def _capture_from_response(self, response: Any) -> None:
        metadata = self._extract_metadata(response)

        thought_keys = ["private_thought", "thought", "reasoning", "trace", "analysis", "logs"]
        for key in thought_keys:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                self.captured_thoughts.append(value.strip())

        raw_tool_calls = (
            metadata.get("tool_calls")
            or metadata.get("tools")
            or metadata.get("actions")
            or metadata.get("events")
            or metadata.get("tool_usage")
            or getattr(response, "tool_calls", None)
            or getattr(response, "tools", None)
            or getattr(response, "actions", None)
        )
        if raw_tool_calls:
            self.captured_tool_calls.extend(self._normalize_tool_calls(raw_tool_calls))

    def _extract_metadata(self, response: Any) -> Dict[str, Any]:
        if isinstance(response, dict):
            metadata = response.get("metadata")
            if isinstance(metadata, dict):
                return metadata
            return response

        metadata = getattr(response, "metadata", None)
        if isinstance(metadata, dict):
            return metadata

        payload = {}
        for attr in ("raw", "result", "output", "__dict__"):
            value = getattr(response, attr, None)
            if isinstance(value, dict):
                payload.update(value)

        # CrewAI task outputs are often list-like objects with useful trace data.
        task_outputs = getattr(response, "tasks_output", None)
        if isinstance(task_outputs, list):
            payload["task_outputs"] = [self._to_dict(item) for item in task_outputs]

        return payload

    def _to_dict(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        if hasattr(value, "__dict__"):
            return value.__dict__
        return value

    def _normalize_tool_calls(self, raw_calls: Any) -> List[Dict[str, Any]]:
        if isinstance(raw_calls, dict):
            raw_calls = [raw_calls]
        if not isinstance(raw_calls, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for call in raw_calls:
            data = self._to_dict(call)
            if not isinstance(data, dict):
                continue

            nested = data.get("tool") if isinstance(data.get("tool"), dict) else None
            tool_as_str = data.get("tool") if isinstance(data.get("tool"), str) else None
            name = (
                data.get("name")
                or data.get("tool_name")
                or tool_as_str
                or data.get("tool_used")
                or data.get("id")
                or (nested.get("name") if nested else None)
            )

            args = (
                data.get("arguments")
                or data.get("args")
                or data.get("parameters")
                or data.get("kwargs")
                or data.get("tool_input")
                or data.get("input")
                or (nested.get("arguments") if nested else None)
                or {}
            )

            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"raw": args}

            if not isinstance(args, dict):
                args = {"value": args}

            if name:
                normalized.append({"name": name, "arguments": args})

        return normalized

    def _extract_final_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response

        if isinstance(response, dict):
            for key in ("raw", "output", "content", "result", "final_output", "response", "text"):
                value = response.get(key)
                if isinstance(value, str) and value:
                    return value
            return str(response)

        for attr in ("raw", "output", "content", "result", "final_output", "response", "text"):
            value = getattr(response, attr, None)
            if isinstance(value, str) and value:
                return value

        return str(response)


setattr(ECPCrewAIAdapter, "step", on_step(ECPCrewAIAdapter.step))
agent()(ECPCrewAIAdapter)
