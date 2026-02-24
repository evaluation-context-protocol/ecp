from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Callable, Dict, List, Optional

from ecp import Result, agent, on_step


class ECPLlamaIndexAdapter:
    """
    Wraps a LlamaIndex workflow-like agent (for example FunctionAgent)
    and exposes it as an ECP-compatible agent.
    """

    def __init__(
        self,
        workflow: Any,
        name: str = "LlamaIndexAgent",
        input_mapper: Optional[Callable[[str], Any]] = None,
        run_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self.workflow = workflow
        self.name = name
        self.input_mapper = input_mapper or (lambda text: {"user_msg": text})
        self.run_kwargs = run_kwargs or {}

        self.captured_thoughts: List[str] = []
        self.captured_tool_calls: List[Dict[str, Any]] = []

        # Same metadata contract used by server initialize.
        self._ecp_meta = {"name": name}

    def step(self, input_text: str) -> Result:
        self.captured_thoughts = []
        self.captured_tool_calls = []

        response = self._run_workflow(input_text)
        self._capture_from_response(response)
        final_text = self._extract_final_text(response)

        return Result(
            status="done",
            public_output=final_text,
            private_thought="\n".join(self.captured_thoughts) if self.captured_thoughts else None,
            tool_calls=self.captured_tool_calls or None,
        )

    def _build_run_kwargs(self, input_text: str) -> Dict[str, Any]:
        mapped = self.input_mapper(input_text)
        if isinstance(mapped, dict):
            return {**self.run_kwargs, **mapped}

        kwargs = dict(self.run_kwargs)
        kwargs["user_msg"] = mapped
        return kwargs

    def _run_workflow(self, input_text: str) -> Any:
        kwargs = self._build_run_kwargs(input_text)

        async def _invoke() -> Any:
            return await self.workflow.run(**kwargs)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_invoke())

        return self._run_coroutine_in_thread(_invoke)

    def _run_coroutine_in_thread(self, coro_factory: Callable[[], Any]) -> Any:
        outcome: Dict[str, Any] = {}

        def _runner() -> None:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                outcome["result"] = loop.run_until_complete(coro_factory())
            except Exception as exc:  # pragma: no cover - exercised by behavior checks
                outcome["error"] = exc
            finally:
                try:
                    loop.close()
                finally:
                    asyncio.set_event_loop(None)

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()

        if "error" in outcome:
            raise outcome["error"]

        return outcome.get("result")

    def _capture_from_response(self, response: Any) -> None:
        metadata = self._extract_metadata(response)
        if not metadata:
            return

        thought_keys = ["private_thought", "thought", "reasoning", "trace", "analysis"]
        for key in thought_keys:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                self.captured_thoughts.append(value.strip())

        raw_tool_calls = (
            metadata.get("tool_calls")
            or metadata.get("tools")
            or getattr(response, "tool_calls", None)
            or metadata.get("events")
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

        raw = getattr(response, "raw", None)
        if isinstance(raw, dict):
            metadata = raw.get("metadata")
            if isinstance(metadata, dict):
                return metadata
            return raw

        return {}

    def _normalize_tool_calls(self, raw_calls: Any) -> List[Dict[str, Any]]:
        if isinstance(raw_calls, dict):
            raw_calls = [raw_calls]
        if not isinstance(raw_calls, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for call in raw_calls:
            if hasattr(call, "dict"):
                data = call.dict()
            elif hasattr(call, "model_dump"):
                data = call.model_dump()
            elif hasattr(call, "__dict__"):
                data = call.__dict__
            else:
                data = call

            if not isinstance(data, dict):
                continue

            name = data.get("name") or data.get("tool") or data.get("id")
            args = (
                data.get("arguments")
                or data.get("args")
                or data.get("parameters")
                or data.get("kwargs")
                or {}
            )

            function = data.get("function")
            if isinstance(function, dict):
                name = name or function.get("name")
                args = args or function.get("arguments") or {}

            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"raw": args}

            normalized.append({"name": name, "arguments": args})

        return normalized

    def _extract_final_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response

        if isinstance(response, dict):
            messages = response.get("messages")
            if isinstance(messages, list):
                content = self._last_message_content(messages)
                if content:
                    return content

            for key in ("response", "output", "content", "text"):
                value = response.get(key)
                if isinstance(value, str) and value:
                    return value

            return str(response)

        if isinstance(response, list):
            content = self._last_message_content(response)
            if content:
                return content

        for attr in ("response", "output", "content", "text", "message"):
            value = getattr(response, attr, None)
            if isinstance(value, str) and value:
                return value

        return str(response)

    def _last_message_content(self, messages: List[Any]) -> Optional[str]:
        for message in reversed(messages):
            if isinstance(message, dict):
                content = message.get("content")
            else:
                content = getattr(message, "content", None)

            if isinstance(content, str) and content:
                return content

        return None


setattr(ECPLlamaIndexAdapter, "step", on_step(ECPLlamaIndexAdapter.step))
agent()(ECPLlamaIndexAdapter)
