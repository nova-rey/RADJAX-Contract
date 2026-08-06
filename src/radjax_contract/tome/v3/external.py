"""Governed comparison and externally supplied v3 evidence interfaces."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from radjax_contract.tome.v3.codec import canonical_base64_decode, fv3
from radjax_contract.tome.v3.issues import TomeV3ValidationError, ValidationPhaseV3
from radjax_contract.tome.v3.models import (
    ArchiveReceiptReportV3,
    AttestationRequirement,
    ExternalAttestationReportV3,
    GovernedComparisonReportV3,
    StandardIntegrityReportV3,
)
from radjax_contract.tome.v3.schema import (
    CONTRACT_VERSION,
    SEMANTIC_PROFILE_ID,
)
from radjax_contract.tome.v3.strict_json import loads


def _external_file(
    artifact: Path, supplied: Path, *, phase: ValidationPhaseV3
) -> bytes:
    try:
        supplied.resolve().relative_to(artifact.resolve())
    except ValueError:
        pass
    else:
        raise TomeV3ValidationError("external_evidence_inside_artifact", phase=phase)
    try:
        return supplied.read_bytes()
    except OSError as exc:
        raise TomeV3ValidationError(
            "external_evidence_unavailable", phase=phase
        ) from exc


def _closed(
    value: Any,
    required: set[str],
    optional: set[str],
    *,
    phase: ValidationPhaseV3,
    code: str,
) -> Mapping[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value) - required - optional
        or required - set(value)
    ):
        raise TomeV3ValidationError(code, phase=phase)
    return value


def _wire_int(value: Any, *, phase: ValidationPhaseV3, code: str) -> int:
    """Normalize a nonsemantic JSON integer lexeme in an external receipt."""

    try:
        result = int(str(value))
    except (TypeError, ValueError) as exc:
        raise TomeV3ValidationError(code, phase=phase) from exc
    if str(result) != str(value) or result < 0:
        raise TomeV3ValidationError(code, phase=phase)
    return result


def compare_governed_v3(
    artifact: Path,
    standard: StandardIntegrityReportV3,
    expected_path: Path,
    identity: Mapping[str, Any],
) -> GovernedComparisonReportV3:
    phase = ValidationPhaseV3.GOVERNED_COMPARISON
    expected = loads(
        _external_file(artifact, expected_path, phase=phase).decode("utf-8", "strict"),
        phase=phase,
    )
    required = {
        "schema_version",
        "expected_semantic_root",
        "expected_authority_identity",
        "expected_contract_version",
        "expected_profile_id",
        "expected_policy_identity",
    }
    value = _closed(
        expected,
        required,
        {"artifact_reference"},
        phase=phase,
        code="governed_comparison_invalid",
    )
    if (
        value["schema_version"] != "radjax_tome_governed_comparison_v1"
        or value["expected_contract_version"] != CONTRACT_VERSION
        or value["expected_profile_id"] != SEMANTIC_PROFILE_ID
    ):
        raise TomeV3ValidationError("governed_comparison_binding_mismatch", phase=phase)
    matches = (
        value["expected_semantic_root"] == standard.semantic_root
        and value["expected_authority_identity"]
        == identity["semantic_authority_identity"]
        and value["expected_policy_identity"] == identity["behavioral_policy_identity"]
    )
    return GovernedComparisonReportV3(
        standard, value["expected_semantic_root"], matches
    )


def validate_archive_receipt_v3(
    archive: Path, receipt_path: Path
) -> ArchiveReceiptReportV3:
    phase = ValidationPhaseV3.EXTERNAL_ATTESTATION
    receipt = loads(receipt_path.read_text(encoding="utf-8"), phase=phase)
    value = _closed(
        receipt,
        {
            "schema_version",
            "algorithm_id",
            "archive_sha256",
            "archive_size_bytes",
            "transport",
        },
        {"artifact_reference"},
        phase=phase,
        code="archive_receipt_invalid",
    )
    if (
        value["schema_version"] != "radjax_tome_archive_receipt_v1"
        or value["algorithm_id"] != "sha256"
    ):
        raise TomeV3ValidationError("archive_receipt_unsupported", phase=phase)
    raw = archive.read_bytes()
    matches = "sha256:" + hashlib.sha256(raw).hexdigest() == value[
        "archive_sha256"
    ] and len(raw) == _wire_int(
        value["archive_size_bytes"],
        phase=phase,
        code="archive_receipt_invalid",
    )
    return ArchiveReceiptReportV3(archive, matches, value["archive_sha256"])


def verify_attestation_v3(
    artifact: Path,
    standard: StandardIntegrityReportV3,
    identity: Mapping[str, Any],
    attestation_path: Path | None,
    *,
    requirement: AttestationRequirement,
    evaluation_time_utc: datetime,
) -> ExternalAttestationReportV3:
    phase = ValidationPhaseV3.EXTERNAL_ATTESTATION
    if attestation_path is None:
        if requirement is AttestationRequirement.REQUIRED:
            raise TomeV3ValidationError("external_attestation_unavailable", phase=phase)
        return ExternalAttestationReportV3(
            standard, requirement, "not_supplied_optional", None, evaluation_time_utc
        )
    raw = _external_file(artifact, attestation_path, phase=phase)
    attestation = loads(raw.decode("utf-8", "strict"), phase=phase)
    required = {
        "schema_version",
        "semantic_root",
        "semantic_authority_identity",
        "contract_version",
        "semantic_profile_id",
        "behavioral_policy_identity",
        "artifact_reference",
        "issuer_id",
        "issued_at",
        "expires_at",
        "envelope_algorithm_id",
        "envelope",
    }
    value = _closed(
        attestation, required, set(), phase=phase, code="external_attestation_invalid"
    )
    if (
        value["schema_version"] != "radjax_tome_external_attestation_v1"
        or value["envelope_algorithm_id"] != "fv3_raw_base64_v1"
    ):
        raise TomeV3ValidationError("external_attestation_unsupported", phase=phase)
    binding = {
        key: value[key]
        for key in sorted(required - {"envelope"}, key=lambda item: item.encode())
    }
    if canonical_base64_decode(value["envelope"]) != fv3(binding):
        raise TomeV3ValidationError(
            "external_attestation_binding_mismatch", phase=phase
        )
    if value["expires_at"] is not None:
        try:
            expiry = datetime.fromisoformat(value["expires_at"].replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise TomeV3ValidationError(
                "external_attestation_time_invalid", phase=phase
            ) from exc
        if evaluation_time_utc.astimezone(UTC) > expiry.astimezone(UTC):
            raise TomeV3ValidationError("external_attestation_expired", phase=phase)
    matches = (
        value["semantic_root"] == standard.semantic_root
        and value["semantic_authority_identity"]
        == identity["semantic_authority_identity"]
        and value["behavioral_policy_identity"]
        == identity["behavioral_policy_identity"]
        and value["contract_version"] == CONTRACT_VERSION
        and value["semantic_profile_id"] == SEMANTIC_PROFILE_ID
    )
    if not matches:
        raise TomeV3ValidationError("external_attestation_mismatch", phase=phase)
    return ExternalAttestationReportV3(
        standard, requirement, "verified", value["semantic_root"], evaluation_time_utc
    )
