"""End-to-end public proof graph and streaming checks for a v3 test package."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from radjax_contract.tome.v3.codec import (
    DOMAIN_LABELS,
    canonical_base64_encode,
    digest,
    fv3,
    logical_record_id,
    record_sequence_digest,
    semantic_root,
)
from radjax_contract.tome.v3.issues import TomeV3ValidationError
from radjax_contract.tome.v3.models import AttestationRequirement
from radjax_contract.tome.v3.validation import (
    compare_governed_tome_artifact_v3,
    open_tome_artifact_v3,
    validate_tome_artifact_v3,
    verify_external_tome_attestation_v3,
)


def _raw(value: object, *, jsonl: bool = False) -> bytes:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return encoded + b"\n" if jsonl else encoded


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _ref(
    path: str, raw: bytes, schema_version: str, *, record_count: int | None = None
) -> dict[str, object]:
    result: dict[str, object] = {
        "path": path,
        "sha256": _digest(raw),
        "size_bytes": len(raw),
        "schema_version": schema_version,
    }
    if record_count is not None:
        result["record_count"] = record_count
    return result


def _write(path: Path, relative: str, raw: bytes) -> None:
    member = path / relative
    member.parent.mkdir(parents=True, exist_ok=True)
    member.write_bytes(raw)


def _valid_artifact(root: Path) -> Path:
    vectors = json.loads(
        Path(
            "src/radjax_contract/contracts/radjax_tome/v3/vectors/tome_provenance_v3_vectors.json"
        ).read_text()
    )
    vector = vectors["normative_root_vectors"][0]
    context = vector["semantic_context"]
    wire_record = vector["ordered_records"][0]
    record = {
        key: value for key, value in wire_record.items() if key != "selection_index"
    }
    logical_id = logical_record_id(record)
    authority = context["authority"]
    policy = context["behavioral_policy"]
    authority_identity = digest(DOMAIN_LABELS["semantic_authority"], authority)
    policy_identity = digest(DOMAIN_LABELS["behavioral_policy"], policy)
    sequence = record_sequence_digest([record])
    identity_without_root = {
        "schema_version": "radjax_tome_semantic_identity_v3",
        "contract_version": "radjax_tome_artifact_contract@3.0.0",
        "semantic_profile_id": "selected_exemplar_semantic_profile_v3",
        "semantic_authority_identity": authority_identity,
        "behavioral_policy_identity": policy_identity,
        "record_count": 1,
        "ordered_record_sequence_digest": sequence,
    }
    identity = {
        **identity_without_root,
        "semantic_root": semantic_root(identity_without_root),
    }
    shard_path = "selected_exemplars/shards/shard-00000.jsonl"
    shard_raw = _raw(record, jsonl=True)
    payload_index_path = "selected_exemplars/payload-index.jsonl"
    payload_index_raw = _raw(
        {
            "logical_record_id": logical_id,
            "selection_index": 0,
            "shard_id": 0,
            "row": 0,
        },
        jsonl=True,
    )
    shard_index_path = "selected_exemplars/payload-shards.jsonl"
    shard_index_raw = _raw(
        {
            "shard_id": 0,
            "path": shard_path,
            "sha256": _digest(shard_raw),
            "size_bytes": len(shard_raw),
            "first_selection_index": 0,
            "record_count": 1,
        },
        jsonl=True,
    )
    identity_path = "provenance/semantic-identity.json"
    authority_path = "provenance/semantic-authority.json"
    policy_path = "provenance/behavioral-policy.json"
    caps_path = "provenance/capabilities.json"
    layout_path = "selected_exemplars/layout.json"
    identity_raw, authority_raw, policy_raw = (
        _raw(identity),
        _raw(authority),
        _raw(policy),
    )
    caps_raw = _raw(
        {
            "schema_version": "radjax_tome_capabilities_v1",
            "required": ["standard_integrity_v3", "streaming_shard_receipts_v3"],
            "optional": [],
        }
    )
    layout = {
        "schema_version": "radjax_tome_payload_layout_v2",
        "semantic_identity_ref": _ref(
            identity_path, identity_raw, "radjax_tome_semantic_identity_v3"
        ),
        "payload_index_ref": _ref(
            payload_index_path,
            payload_index_raw,
            "radjax_tome_payload_index_v3",
            record_count=1,
        ),
        "shard_index_ref": _ref(
            shard_index_path,
            shard_index_raw,
            "radjax_tome_payload_shard_index_v2",
            record_count=1,
        ),
        "record_count": 1,
        "shard_capacity": 1,
    }
    layout_raw = _raw(layout)
    members = {
        identity_path: (identity_raw, "semantic_identity"),
        authority_path: (authority_raw, "semantic_authority"),
        policy_path: (policy_raw, "behavioral_policy"),
        caps_path: (caps_raw, "capabilities"),
        layout_path: (layout_raw, "payload_layout"),
        payload_index_path: (payload_index_raw, "payload_index"),
        shard_index_path: (shard_index_raw, "payload_shard_index"),
        shard_path: (shard_raw, "payload_shard"),
    }
    inventory_rows = [
        {
            "path": name,
            "sha256": _digest(raw),
            "size_bytes": len(raw),
            "member_role": role,
            "classification": "integrity_or_provenance",
            "required_for_standard_validation": True,
        }
        for name, (raw, role) in members.items()
    ]
    inventory_path = "manifests/content-manifest-inventory.jsonl"
    inventory_raw = b"".join(_raw(row, jsonl=True) for row in inventory_rows)
    header_path = "manifests/content-manifest-header.json"
    header = {
        "schema_version": "tome_content_manifest_header_v4",
        "contract_version": "radjax_tome_artifact_contract@3.0.0",
        "profile_id": "selected_exemplar_semantic_profile_v3",
        "capabilities_ref": _ref(caps_path, caps_raw, "radjax_tome_capabilities_v1"),
        "semantic_identity_ref": _ref(
            identity_path, identity_raw, "radjax_tome_semantic_identity_v3"
        ),
        "layout_ref": _ref(layout_path, layout_raw, "radjax_tome_payload_layout_v2"),
        "inventory_ref": _ref(
            inventory_path, inventory_raw, "tome_content_manifest_inventory_v4"
        ),
        "entry_count": len(inventory_rows),
    }
    header_raw = _raw(header)
    cover = {
        "schema_version": "radjax_tome_cover_v5",
        "contract_version": "radjax_tome_artifact_contract@3.0.0",
        "package": {
            "profile_id": "selected_exemplar_semantic_profile_v3",
            "transport": "directory",
        },
        "capabilities_ref": _ref(caps_path, caps_raw, "radjax_tome_capabilities_v1"),
        "semantic_identity_ref": _ref(
            identity_path, identity_raw, "radjax_tome_semantic_identity_v3"
        ),
        "semantic_authority_ref": _ref(
            authority_path, authority_raw, "radjax_tome_semantic_authority_v1"
        ),
        "behavioral_policy_ref": _ref(
            policy_path, policy_raw, "radjax_tome_behavioral_policy_v1"
        ),
        "manifest_header_ref": _ref(
            header_path, header_raw, "tome_content_manifest_header_v4"
        ),
        "record_count": 1,
        "shard_count": 1,
    }
    _write(root, "cover_page.json", _raw(cover))
    _write(root, header_path, header_raw)
    _write(root, inventory_path, inventory_raw)
    for name, (raw, _) in members.items():
        _write(root, name, raw)
    return root


def test_standard_validation_and_streaming_verify_before_yield(tmp_path: Path) -> None:
    artifact = _valid_artifact(tmp_path / "artifact")
    report = validate_tome_artifact_v3(artifact)
    assert report.record_count == 1
    with open_tome_artifact_v3(artifact) as reader:
        assert len(list(reader)) == 1
    shard = artifact / "selected_exemplars/shards/shard-00000.jsonl"
    shard.write_bytes(shard.read_bytes() + b" ")
    with pytest.raises(TomeV3ValidationError, match="inventory_member_mismatch"):
        open_tome_artifact_v3(artifact)


def test_governed_and_external_modes_use_expected_evidence_outside_artifact(
    tmp_path: Path,
) -> None:
    artifact = _valid_artifact(tmp_path / "artifact")
    identity = json.loads((artifact / "provenance/semantic-identity.json").read_text())
    expected = {
        "schema_version": "radjax_tome_governed_comparison_v1",
        "expected_semantic_root": identity["semantic_root"],
        "expected_authority_identity": identity["semantic_authority_identity"],
        "expected_contract_version": identity["contract_version"],
        "expected_profile_id": identity["semantic_profile_id"],
        "expected_policy_identity": identity["behavioral_policy_identity"],
    }
    expected_path = tmp_path / "governed.json"
    expected_path.write_bytes(_raw(expected))
    assert compare_governed_tome_artifact_v3(artifact, expected_path).matches
    expected["expected_semantic_root"] = "sha256:" + "0" * 64
    expected_path.write_bytes(_raw(expected))
    assert not compare_governed_tome_artifact_v3(artifact, expected_path).matches

    attestation = {
        "schema_version": "radjax_tome_external_attestation_v1",
        "semantic_root": identity["semantic_root"],
        "semantic_authority_identity": identity["semantic_authority_identity"],
        "contract_version": identity["contract_version"],
        "semantic_profile_id": identity["semantic_profile_id"],
        "behavioral_policy_identity": identity["behavioral_policy_identity"],
        "artifact_reference": "release/test",
        "issuer_id": "independent-test-domain",
        "issued_at": "2026-08-06T00:00:00Z",
        "expires_at": "2027-08-06T00:00:00Z",
        "envelope_algorithm_id": "fv3_raw_base64_v1",
    }
    binding = {
        key: attestation[key]
        for key in sorted(attestation, key=lambda key: key.encode())
    }
    attestation["envelope"] = canonical_base64_encode(fv3(binding))
    attestation_path = tmp_path / "attestation.json"
    attestation_path.write_bytes(_raw(attestation))
    result = verify_external_tome_attestation_v3(
        artifact,
        attestation_path,
        requirement=AttestationRequirement.REQUIRED,
        evaluation_time_utc=datetime(2026, 8, 6, tzinfo=UTC),
    )
    assert result.status == "verified"
    with pytest.raises(
        TomeV3ValidationError, match="external_evidence_inside_artifact"
    ):
        verify_external_tome_attestation_v3(
            artifact,
            artifact / "provenance/semantic-identity.json",
            requirement=AttestationRequirement.REQUIRED,
            evaluation_time_utc=datetime(2026, 8, 6, tzinfo=UTC),
        )
