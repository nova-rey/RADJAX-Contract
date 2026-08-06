"""Stable issue vocabulary for the unreleased Tome artifact Contract v3."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ValidationPhaseV3(IntEnum):
    DISCOVERY = 1
    DISPATCH = 2
    RAW_MEMBERS = 3
    GRAPH = 4
    INDEXES = 5
    SEMANTIC_RECORDS = 6
    SEMANTIC_ROOT = 7
    GOVERNED_COMPARISON = 8
    EXTERNAL_ATTESTATION = 9


@dataclass(frozen=True, order=True)
class IssueV3:
    """One deterministic v3 validation finding.

    Codes are intentionally stable machine values rather than exception prose.
    The tuple sort order makes reports reproducible across transports.
    """

    phase: ValidationPhaseV3
    code: str
    location: str = ""
    detail: str = ""


class TomeV3ValidationError(ValueError):
    """Raised by the fail-closed v3 decoder and validator."""

    def __init__(
        self, code: str, *, phase: ValidationPhaseV3, location: str = ""
    ) -> None:
        self.issue = IssueV3(phase, code, location)
        super().__init__(code if not location else f"{code}:{location}")
