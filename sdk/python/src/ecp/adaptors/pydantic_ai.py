from typing import Any, Callable, Dict, List, Optional, Union
import json

from ecp import Result, agent, on_step


class ECPPydanticAIAdapter:
    """
    Wraps a PydanticAI Agent and exposes it as an ECP-compatible agent.
    """

    def __init__(
        self,
        pydantic_agent: Any,
        name: str = "PydanticAIAgent",
        run_kwargs: Optional[Dict[str, Any]] = None,
        include_all_messages: bool = False,
    ):
        """
        Initialize the PydanticAI adapter.

        Args:
            pydantic_agent: The PydanticAI Agent instance.
            name: Optional name for the agent.
            run_kwargs: Optional keyword arguments to pass to the agent's run_sync method.
            include_all_messages: If True, extract thoughts/tool calls from all messages in the run,
                                 otherwise only from new messages.
        """
        self.agent = pydantic_agent
        self.name = name
        self.run_kwargs = run_kwargs or {}
        self.include_all_messages = include_all_messages

        self.captured_thoughts: List[str] = []
        self.captured_tool_calls: List[Dict[str, Any]] = []

        self._ecp_meta = {"name": name}

    def step(self, input_text: str) -> Result:
        self.captured_thoughts = []
        self.captured_tool_calls = []

        # PydanticAI run_sync
        run_kwargs = dict(self.run_kwargs)
        result = self.agent.run_sync(input_text, **run_kwargs)

        # 1. Capture thoughts and tool calls from messages
        self._capture_from_result(result)

        # 2. Capture usage metadata as a thought
        try:
            usage = result.usage()
            if usage:
                usage_str = f"Usage: {usage.input_tokens} input, {usage.output_tokens} output tokens ({usage.requests} requests)"
                self.captured_thoughts.append(usage_str)
        except Exception:
            pass

        # 3. Format public output
        # If the result has structured 'data', we prefer that. 
        # If it's a Pydantic model, dump it correctly.
        public_output = ""
        try:
            if hasattr(result, "data") and result.data is not None:
                if hasattr(result.data, "model_dump_json"):
                    public_output = result.data.model_dump_json()
                elif hasattr(result.data, "model_dump"):
                    public_output = str(result.data.model_dump())
                else:
                    public_output = str(result.data)
            else:
                public_output = str(result.output)
        except Exception:
            public_output = str(getattr(result, "output", ""))

        return Result(
            status="done",
            public_output=public_output,
            private_thought="\n".join(self.captured_thoughts) if self.captured_thoughts else None,
            tool_calls=self.captured_tool_calls or None,
        )

    def _capture_from_result(self, result: Any) -> None:
        """
        Extract thoughts and tool calls from the RunResult.
        """
        try:
            # Get messages to process
            if self.include_all_messages:
                messages = result.all_messages()
            else:
                messages = result.new_messages()
        except Exception:
            return

        if not isinstance(messages, list) or not messages:
            return

        # The last ModelResponse is the final one containing public_output
        responses = [m for m in messages if getattr(m, "kind", None) == "response"]
        last_response = responses[-1] if responses else None
        
        for msg in responses:
            parts = getattr(msg, "parts", [])
            for part in parts:
                part_kind = getattr(part, "part_kind", None)

                # Capture explicit reasoning (ThinkingPart)
                if part_kind == "thinking":
                    content = getattr(part, "content", "")
                    if content:
                        self.captured_thoughts.append(content)
                
                # Capture reasoning TextParts
                elif part_kind == "text":
                    content = getattr(part, "content", "")
                    # A text part is a thought if:
                    # 1. It's in a message that also has tool calls
                    # 2. It's in a message that is NOT the very last response of the run
                    has_tool_calls = any(getattr(p, "part_kind", "") in ("tool-call", "tool_call") for p in parts)
                    
                    if msg is not last_response or has_tool_calls:
                        if content and content.strip():
                            self.captured_thoughts.append(content.strip())
                
                # Capture tool calls
                elif part_kind in ("tool-call", "tool_call"):
                    tool_name = getattr(part, "tool_name", None)
                    args = {}
                    
                    if hasattr(part, "args_as_dict"):
                        try:
                            args = part.args_as_dict()
                        except Exception:
                            args = getattr(part, "args", {})
                    else:
                        args = getattr(part, "args", {})

                    if tool_name:
                        self.captured_tool_calls.append({
                            "name": tool_name,
                            "arguments": args
                        })

    def _to_json_serializable(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return value


setattr(ECPPydanticAIAdapter, "step", on_step(ECPPydanticAIAdapter.step))
agent()(ECPPydanticAIAdapter)
