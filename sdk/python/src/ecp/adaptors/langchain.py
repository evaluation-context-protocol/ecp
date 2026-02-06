from typing import Any, Callable, Dict, List, Optional
import json
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

# We use your SDK's Result object
from ecp import Result, agent, on_step

class ECPLangChainAdapter(BaseCallbackHandler):
    """
    Hooks into LangChain to capture 'Thoughts' (LLM generations) 
    separate from 'Final Output'.
    """
    def __init__(self, runnable, name="LangChainAgent", input_mapper: Optional[Callable[[str], Any]] = None):
        self.runnable = runnable
        self.name = name
        self.input_mapper = input_mapper or (lambda text: text)
        self.captured_thoughts = []
        self.captured_tool_calls: List[Dict[str, Any]] = []
        self.last_output = None
        
        # Register this class as an ECP Agent dynamically!
        # This is equivalent to putting @agent on top of it.
        self._ecp_meta = {"name": name}

    # --- ECP Hooks (The runtime calls these) ---

    def step(self, input_text: str):
        """The function ECP calls."""
        # Clear previous run data
        self.captured_thoughts = []
        self.captured_tool_calls = []
        self.last_output = None
        
        # Run LangChain with THIS class as a callback
        # This is where the magic happens. We inject 'self' into the run.
        response = self.runnable.invoke(
            self.input_mapper(input_text),
            config={"callbacks": [self]}
        )
        
        # Handle different LangChain output types (String vs Dict)
        final_text = self._extract_final_text(response)

        return Result(
            status="done",
            public_output=final_text,
            # We join all the intermediate LLM tokens/thoughts we caught
            private_thought="\n".join(self.captured_thoughts),
            tool_calls=self.captured_tool_calls or None
        )

    # --- LangChain Hooks (LangChain calls these) ---

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> Any:
        # We could log the prompt here if we wanted
        pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> Any:
        """Capture what the LLM actually generated internally."""
        for generations in response.generations:
            for gen in generations:
                # This is the "Thought" (or part of it)
                text = getattr(gen, "text", None)
                if text:
                    self.captured_thoughts.append(text)

                message = getattr(gen, "message", None)
                raw_tool_calls: Optional[List[Any]] = None
                if message is not None:
                    if hasattr(message, "tool_calls"):
                        raw_tool_calls = message.tool_calls
                    elif hasattr(message, "additional_kwargs"):
                        raw_tool_calls = message.additional_kwargs.get("tool_calls")

                if raw_tool_calls:
                    self.captured_tool_calls.extend(self._normalize_tool_calls(raw_tool_calls))

    def _normalize_tool_calls(self, raw_calls: List[Any]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for call in raw_calls:
            if hasattr(call, "dict"):
                data = call.dict()
            elif hasattr(call, "__dict__"):
                data = call.__dict__
            else:
                data = call

            if not isinstance(data, dict):
                continue

            name = data.get("name") or data.get("tool") or data.get("id")
            args = data.get("arguments") or data.get("args") or data.get("parameters") or {}
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
            return response.get("output") or response.get("content") or str(response)

        if isinstance(response, list):
            content = self._last_message_content(response)
            if content:
                return content

        if hasattr(response, "content"):
            return getattr(response, "content")

        return str(response)

    def _last_message_content(self, messages: List[Any]) -> Optional[str]:
        for msg in reversed(messages):
            if isinstance(msg, dict):
                content = msg.get("content")
            else:
                content = getattr(msg, "content", None)
            if content:
                return content
        return None

# --- Monkey Patching to make it work with @on_step ---
# Since this is an adapter, we manually bind the 'step' method to the 'step' hook.
# In a real production SDK, we'd do this cleaner, but this works for v0.1.
setattr(ECPLangChainAdapter, "step", on_step(ECPLangChainAdapter.step))
agent()(ECPLangChainAdapter) # Apply the @agent decorator logic manually
