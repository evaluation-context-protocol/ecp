"""
ECP entrypoint for the refund-desk crew.

The whole integration: import the crew, wrap it, serve it. `crew.py` is untouched.
"""

from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent

# Load keys from a .env next to this file, falling back to the repo root.
# override=False so a real environment variable always wins.
load_dotenv(HERE / ".env", override=False)
load_dotenv(HERE.parents[1] / ".env", override=False)

from crew import build_crew  # noqa: E402
from ecp import serve  # noqa: E402
from ecp.adaptors.crewai import ECPCrewAIAdapter  # noqa: E402
from tools import mark_step  # noqa: E402


def _inputs(text: str) -> dict:
    # Mark where this step begins in the tool log, then hand the text to the crew.
    mark_step(text)
    return {"customer_request": text}


ecp_agent = ECPCrewAIAdapter(build_crew(), name="RefundDeskCrew", input_mapper=_inputs)

# Tell the runtime what this agent can report, so a manifest asking for something
# it cannot produce fails clearly instead of as N identical grader failures.
ecp_agent._ecp_meta["capabilities"] = {"tool_calls": {}, "evaluation_context": {}}

if __name__ == "__main__":
    serve(ecp_agent)
