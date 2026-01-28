from typing import Any, Dict, List
from uuid import UUID
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

# We use your SDK's Result object
from ecp import Result, agent, on_step

class ECPLangChainAdapter(BaseCallbackHandler):
    """
    Hooks into LangChain to capture 'Thoughts' (LLM generations) 
    separate from 'Final Output'.
    """
    def __init__(self, runnable, name="LangChainAgent"):
        self.runnable = runnable
        self.name = name
        self.captured_thoughts = []
        self.last_output = None
        
        # Register this class as an ECP Agent dynamically!
        # This is equivalent to putting @agent on top of it.
        self._ecp_meta = {"name": name}

    # --- ECP Hooks (The runtime calls these) ---

    def step(self, input_text: str):
        """The function ECP calls."""
        # Clear previous run data
        self.captured_thoughts = []
        self.last_output = None
        
        # Run LangChain with THIS class as a callback
        # This is where the magic happens. We inject 'self' into the run.
        response = self.runnable.invoke(
            input_text, 
            config={"callbacks": [self]}
        )
        
        # Handle different LangChain output types (String vs Dict)
        final_text = ""
        if isinstance(response, str):
            final_text = response
        elif isinstance(response, dict):
            # Try standard keys
            final_text = response.get("output") or response.get("content") or str(response)
        else:
            final_text = str(response)

        return Result(
            status="done",
            public_output=final_text,
            # We join all the intermediate LLM tokens/thoughts we caught
            private_thought="\n".join(self.captured_thoughts) 
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
                self.captured_thoughts.append(gen.text)

# --- Monkey Patching to make it work with @on_step ---
# Since this is an adapter, we manually bind the 'step' method to the 'step' hook.
# In a real production SDK, we'd do this cleaner, but this works for v0.1.
setattr(ECPLangChainAdapter, "step", on_step(ECPLangChainAdapter.step))
agent()(ECPLangChainAdapter) # Apply the @agent decorator logic manually