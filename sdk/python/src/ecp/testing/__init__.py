"""
ecp.testing
===========
Test helpers for keeping framework adapters honest.

Adapters translate framework-specific response objects into ECP ``Result``
objects by walking framework internals. When a framework reshapes those
internals the translation breaks silently - ``tool_calls`` comes back empty and
every ``tool_usage`` grader fails, which looks like an agent regression rather
than an adapter bug.

This package closes that gap from two sides:

- :func:`record_fixture` captures a real framework exchange to JSON.
- :func:`replay` re-runs an adapter against that capture with no framework
  install and no API key, so PR CI catches regressions in adapter code.

Re-recording against a newer framework version turns a shape change into a
fixture diff. Running the real demos nightly catches the framework changing
behaviour rather than shape. Both are needed; neither substitutes for the other.
"""

from .fixtures import RecordedObject, rebuild, record
from .replay import (
    AdapterFixture,
    diff_expected,
    record_fixture,
    replay,
    result_to_dict,
)

__all__ = [
    "AdapterFixture",
    "RecordedObject",
    "diff_expected",
    "rebuild",
    "record",
    "record_fixture",
    "replay",
    "result_to_dict",
]
