"""Frozen public reports and private journal values for Tome artifact v3."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from radjax_contract.tome.v3.issues import IssueV3


class AttestationRequirement(StrEnum):
    OPTIONAL = "optional"
    REQUIRED = "required"


@dataclass(frozen=True)
class StandardIntegrityReportV3:
    artifact: Path
    transport: str
    semantic_root: str
    record_count: int
    shard_count: int
    issues: tuple[IssueV3, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class GovernedComparisonReportV3:
    standard: StandardIntegrityReportV3
    expected_semantic_root: str
    matches: bool


@dataclass(frozen=True)
class ExternalAttestationReportV3:
    standard: StandardIntegrityReportV3
    requirement: AttestationRequirement
    status: str
    attestation_semantic_root: str | None
    evaluated_at: datetime


@dataclass(frozen=True)
class ArchiveReceiptReportV3:
    archive: Path
    matches: bool
    expected_sha256: str


@dataclass(frozen=True)
class JournalStateV3:
    transaction_id: str
    configuration_identity: str
    semantic_authority_identity: str
    state: str
    sealed_shards: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    committed_next_selection_index: int = 0
    completion_intent: bool = False
    promotion_marker: bool = False


@dataclass(frozen=True)
class JournalRestartDispositionV3:
    """Private, side-effect-free recovery decision for a validated journal."""

    action: str
    public_visible: bool
