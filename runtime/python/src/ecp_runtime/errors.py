"""
ecp_runtime.errors
==================
Typed execution failures raised by the agent transports.

Every class subclasses ``RuntimeError`` so existing callers that catch
``RuntimeError`` keep working. The subclasses exist so the runner can record a
precise ``exit_reason`` in the audit payload instead of pattern matching on
error message text.
"""


class ECPExecutionError(RuntimeError):
    """Base class for failures encountered while driving an agent."""

    exit_reason = "error"


class ECPTimeoutError(ECPExecutionError):
    """The agent did not answer an RPC inside the configured timeout."""

    exit_reason = "timeout"


class ECPTransportError(ECPExecutionError):
    """The agent crashed, refused a connection, or closed the stream."""

    exit_reason = "transport_error"


class ECPProtocolError(ECPExecutionError):
    """The agent replied, but the reply violates the ECP contract."""

    exit_reason = "protocol_error"


class ECPVersionUnsupported(ECPProtocolError):
    """The runtime and agent do not share a compatible protocol major version."""

    code = -32001


class ECPAgentError(ECPExecutionError):
    """The agent returned a well-formed JSON-RPC error response."""

    exit_reason = "agent_error"


class ECPBudgetExceeded(ECPExecutionError):
    """The run exceeded its wall-clock budget."""

    exit_reason = "max_duration_exceeded"


def exit_reason_for(exc: BaseException) -> str:
    """Map an exception onto a stable audit ``exit_reason`` string."""
    return getattr(exc, "exit_reason", "error")
