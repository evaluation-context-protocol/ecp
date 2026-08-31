"""Wire-level protocol version negotiation for the ECP runtime."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from .errors import ECPVersionUnsupported

PROTOCOL_VERSION = "1.0"
LEGACY_PROTOCOL_VERSION = "0.1"
VERSION_UNSUPPORTED_CODE = ECPVersionUnsupported.code

_PROTOCOL_VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


@dataclass(frozen=True)
class ProtocolNegotiation:
    """The version selected for a runtime-agent session."""

    version: str
    legacy: bool = False


def parse_protocol_version(
    value: object, *, field: str = "protocol_version"
) -> Tuple[int, int]:
    """Parse a ``MAJOR.MINOR`` version or raise a contract validation error."""
    if not isinstance(value, str) or _PROTOCOL_VERSION_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be a MAJOR.MINOR string")
    major, minor = value.split(".", 1)
    return int(major), int(minor)


def negotiate_protocol_version(agent_version: Optional[str]) -> ProtocolNegotiation:
    """Select the common protocol version, preserving versionless legacy agents."""
    if agent_version is None:
        return ProtocolNegotiation(LEGACY_PROTOCOL_VERSION, legacy=True)

    runtime_major, runtime_minor = parse_protocol_version(PROTOCOL_VERSION)
    agent_major, agent_minor = parse_protocol_version(
        agent_version,
        field="agent/initialize result protocol_version",
    )
    if runtime_major != agent_major:
        raise ECPVersionUnsupported(
            f"VERSION_UNSUPPORTED ({VERSION_UNSUPPORTED_CODE}): "
            f"runtime supports protocol {PROTOCOL_VERSION}, but the agent selected {agent_version}"
        )

    return ProtocolNegotiation(f"{runtime_major}.{min(runtime_minor, agent_minor)}")


def initialize_params(config: Optional[dict] = None) -> dict:
    """Build the normative ``agent/initialize`` request parameters."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "config": {} if config is None else config,
    }
