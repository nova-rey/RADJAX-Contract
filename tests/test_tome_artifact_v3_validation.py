"""End-to-end public proof graph and streaming checks for a v3 test package."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from collections.abc import Callable
from copy import deepcopy
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
from radjax_contract.tome.v3.external import validate_archive_receipt_v3
from radjax_contract.tome.v3.issues import TomeV3ValidationError
from radjax_contract.tome.v3.models import AttestationRequirement
from radjax_contract.tome.v3.schema import normalize_semantic_record
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


def _rewrite_inventory_and_cover(
    artifact: Path, mutate: Callable[[list[dict[str, object]]], None]
) -> None:
    """Refresh only the graph receipts needed to exercise inventory semantics.

    The mutation oracle is deliberately independent of the validator: it changes
    the inventory claim, recomputes its containing references, and leaves every
    unrelated member unchanged.  A rejection therefore demonstrates field
    validation rather than detection of a stale digest.
    """

    inventory_path = "manifests/content-manifest-inventory.jsonl"
    header_path = "manifests/content-manifest-header.json"
    rows = [
        json.loads(line)
        for line in (artifact / inventory_path).read_text().splitlines()
    ]
    mutate(rows)
    inventory_raw = b"".join(_raw(row, jsonl=True) for row in rows)
    _write(artifact, inventory_path, inventory_raw)

    header = json.loads((artifact / header_path).read_text())
    header["entry_count"] = len(rows)
    header["inventory_ref"] = _ref(
        inventory_path, inventory_raw, "tome_content_manifest_inventory_v4"
    )
    header_raw = _raw(header)
    _write(artifact, header_path, header_raw)

    cover = json.loads((artifact / "cover_page.json").read_text())
    cover["manifest_header_ref"] = _ref(
        header_path, header_raw, "tome_content_manifest_header_v4"
    )
    _write(artifact, "cover_page.json", _raw(cover))


def _refresh_graph_after_member_change(
    artifact: Path, relative: str, raw: bytes
) -> None:
    """Replace one member and coherently refresh only raw graph receipts."""

    _write(artifact, relative, raw)

    def mutate(rows: list[dict[str, object]]) -> None:
        row = next(item for item in rows if item["path"] == relative)
        row["sha256"] = _digest(raw)
        row["size_bytes"] = len(raw)

    _rewrite_inventory_and_cover(artifact, mutate)


def _refresh_complete_public_graph(artifact: Path) -> None:
    """Refresh all *preceding* public references after a targeted test mutation."""

    def refresh_refs(value: dict[str, object]) -> dict[str, object]:
        for key, candidate in value.items():
            if not key.endswith("_ref") or not isinstance(candidate, dict):
                continue
            path = candidate.get("path")
            if not isinstance(path, str) or not (artifact / path).is_file():
                continue
            raw = (artifact / path).read_bytes()
            candidate["sha256"] = _digest(raw)
            candidate["size_bytes"] = len(raw)
        return value

    layout_path = artifact / "selected_exemplars/layout.json"
    layout = refresh_refs(json.loads(layout_path.read_text()))
    _write(artifact, layout_path.relative_to(artifact).as_posix(), _raw(layout))
    header_path = artifact / "manifests/content-manifest-header.json"
    header = refresh_refs(json.loads(header_path.read_text()))
    _write(artifact, header_path.relative_to(artifact).as_posix(), _raw(header))
    cover_path = artifact / "cover_page.json"
    cover = refresh_refs(json.loads(cover_path.read_text()))
    _write(artifact, cover_path.relative_to(artifact).as_posix(), _raw(cover))

    inventory_path = artifact / "manifests/content-manifest-inventory.jsonl"
    rows = [json.loads(line) for line in inventory_path.read_text().splitlines()]
    for row in rows:
        raw = (artifact / row["path"]).read_bytes()
        row["sha256"] = _digest(raw)
        row["size_bytes"] = len(raw)
    inventory_raw = b"".join(_raw(row, jsonl=True) for row in rows)
    _write(artifact, inventory_path.relative_to(artifact).as_posix(), inventory_raw)
    header = refresh_refs(json.loads(header_path.read_text()))
    _write(artifact, header_path.relative_to(artifact).as_posix(), _raw(header))
    cover = refresh_refs(json.loads(cover_path.read_text()))
    _write(artifact, cover_path.relative_to(artifact).as_posix(), _raw(cover))


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


def _rebuild_from_records(
    artifact: Path, records: list[dict[str, object]], shard_sizes: list[int]
) -> None:
    """Write a coherent test package from records without using the validator.

    It deliberately rebuilds only the documented producer receipts.  Tests then
    make their targeted mutation after this helper returns, so a failure cannot
    be credited to a stale outer receipt.
    """

    assert sum(shard_sizes) == len(records)
    context = json.loads((artifact / "provenance/semantic-authority.json").read_text())
    policy = json.loads((artifact / "provenance/behavioral-policy.json").read_text())
    authority_identity = digest(DOMAIN_LABELS["semantic_authority"], context)
    policy_identity = digest(DOMAIN_LABELS["behavioral_policy"], policy)
    identity_without_root = {
        "schema_version": "radjax_tome_semantic_identity_v3",
        "contract_version": "radjax_tome_artifact_contract@3.0.0",
        "semantic_profile_id": "selected_exemplar_semantic_profile_v3",
        "semantic_authority_identity": authority_identity,
        "behavioral_policy_identity": policy_identity,
        "record_count": len(records),
        "ordered_record_sequence_digest": record_sequence_digest(records),
    }
    identity = {
        **identity_without_root,
        "semantic_root": semantic_root(identity_without_root),
    }
    identity_path = "provenance/semantic-identity.json"
    _write(artifact, identity_path, _raw(identity))
    shard_dir = artifact / "selected_exemplars/shards"
    for old in shard_dir.glob("*.jsonl"):
        old.unlink()
    payload_rows: list[dict[str, object]] = []
    shard_rows: list[dict[str, object]] = []
    offset = 0
    for shard_id, shard_size in enumerate(shard_sizes):
        chunk = records[offset : offset + shard_size]
        member_path = f"selected_exemplars/shards/shard-{shard_id:05d}.jsonl"
        raw = b"".join(_raw(record, jsonl=True) for record in chunk)
        _write(artifact, member_path, raw)
        shard_rows.append(
            {
                "shard_id": shard_id,
                "path": member_path,
                "sha256": _digest(raw),
                "size_bytes": len(raw),
                "first_selection_index": offset,
                "record_count": shard_size,
            }
        )
        payload_rows.extend(
            {
                "logical_record_id": logical_record_id(record),
                "selection_index": offset + row,
                "shard_id": shard_id,
                "row": row,
            }
            for row, record in enumerate(chunk)
        )
        offset += shard_size
    payload_index_path = "selected_exemplars/payload-index.jsonl"
    shard_index_path = "selected_exemplars/payload-shards.jsonl"
    payload_index_raw = b"".join(_raw(row, jsonl=True) for row in payload_rows)
    shard_index_raw = b"".join(_raw(row, jsonl=True) for row in shard_rows)
    _write(artifact, payload_index_path, payload_index_raw)
    _write(artifact, shard_index_path, shard_index_raw)
    layout_path = "selected_exemplars/layout.json"
    layout = json.loads((artifact / layout_path).read_text())
    layout["semantic_identity_ref"] = _ref(
        identity_path, _raw(identity), "radjax_tome_semantic_identity_v3"
    )
    layout["payload_index_ref"] = _ref(
        payload_index_path,
        payload_index_raw,
        "radjax_tome_payload_index_v3",
        record_count=len(records),
    )
    layout["shard_index_ref"] = _ref(
        shard_index_path,
        shard_index_raw,
        "radjax_tome_payload_shard_index_v2",
        record_count=len(shard_rows),
    )
    layout["record_count"] = len(records)
    layout["shard_capacity"] = max(shard_sizes)
    _write(artifact, layout_path, _raw(layout))
    role_by_path = {
        row["path"]: row["member_role"]
        for row in (
            json.loads(line)
            for line in (artifact / "manifests/content-manifest-inventory.jsonl")
            .read_text()
            .splitlines()
        )
    }
    role_by_path.update(
        {
            identity_path: "semantic_identity",
            layout_path: "payload_layout",
            payload_index_path: "payload_index",
            shard_index_path: "payload_shard_index",
        }
    )
    for row in shard_rows:
        role_by_path[row["path"]] = "payload_shard"
    inventory_rows = [
        {
            "path": path,
            "sha256": _digest((artifact / path).read_bytes()),
            "size_bytes": (artifact / path).stat().st_size,
            "member_role": role,
            "classification": "integrity_or_provenance",
            "required_for_standard_validation": True,
        }
        for path, role in sorted(role_by_path.items())
        if (artifact / path).exists()
    ]
    inventory_path = "manifests/content-manifest-inventory.jsonl"
    inventory_raw = b"".join(_raw(row, jsonl=True) for row in inventory_rows)
    _write(artifact, inventory_path, inventory_raw)
    header_path = "manifests/content-manifest-header.json"
    header = json.loads((artifact / header_path).read_text())
    header["semantic_identity_ref"] = _ref(
        identity_path, _raw(identity), "radjax_tome_semantic_identity_v3"
    )
    header["layout_ref"] = _ref(
        layout_path,
        (artifact / layout_path).read_bytes(),
        "radjax_tome_payload_layout_v2",
    )
    header["inventory_ref"] = _ref(
        inventory_path, inventory_raw, "tome_content_manifest_inventory_v4"
    )
    header["entry_count"] = len(inventory_rows)
    header_raw = _raw(header)
    _write(artifact, header_path, header_raw)
    cover = json.loads((artifact / "cover_page.json").read_text())
    cover["semantic_identity_ref"] = _ref(
        identity_path, _raw(identity), "radjax_tome_semantic_identity_v3"
    )
    cover["manifest_header_ref"] = _ref(
        header_path, header_raw, "tome_content_manifest_header_v4"
    )
    cover["record_count"] = len(records)
    cover["shard_count"] = len(shard_rows)
    _write(artifact, "cover_page.json", _raw(cover))


def _two_record_artifact(root: Path, *, shard_sizes: list[int] | None = None) -> Path:
    artifact = _valid_artifact(root)
    original = json.loads(
        (artifact / "selected_exemplars/shards/shard-00000.jsonl").read_text()
    )
    second = deepcopy(original)
    second["selected_example_id"] = "example-b"
    _rebuild_from_records(artifact, [original, second], shard_sizes or [1, 1])
    return artifact


def test_standard_validation_and_streaming_verify_before_yield(tmp_path: Path) -> None:
    artifact = _valid_artifact(tmp_path / "artifact")
    report = validate_tome_artifact_v3(artifact)
    assert report.record_count == 1
    with open_tome_artifact_v3(artifact) as reader:
        assert len(list(reader)) == 1
    shard = artifact / "selected_exemplars/shards/shard-00000.jsonl"
    shard.write_bytes(shard.read_bytes() + b" ")
    with pytest.raises(TomeV3ValidationError, match="corrupt_shard"):
        with open_tome_artifact_v3(artifact) as reader:
            list(reader)


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
    with pytest.raises(TomeV3ValidationError, match="governed_expected_root_mismatch"):
        compare_governed_tome_artifact_v3(artifact, expected_path)

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
    with pytest.raises(TomeV3ValidationError, match="attestation_not_external"):
        verify_external_tome_attestation_v3(
            artifact,
            artifact / "provenance/semantic-identity.json",
            requirement=AttestationRequirement.REQUIRED,
            evaluation_time_utc=datetime(2026, 8, 6, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("selected_position", "1"),
        ("selected_position", True),
        ("selected_score", "0.5"),
        ("selected_score", False),
        ("top_token_ids", ["1"]),
        ("top_probs", [True]),
    ],
)
def test_pc20_closed_semantic_numeric_fields_reject_strings_and_booleans(
    field: str, invalid_value: object
) -> None:
    """PC20: field-selected semantic numeric types never infer JSON strings/bools."""

    vectors = json.loads(
        Path(
            "src/radjax_contract/contracts/radjax_tome/v3/vectors/"
            "tome_provenance_v3_vectors.json"
        ).read_text()
    )
    record = deepcopy(vectors["normative_root_vectors"][0]["ordered_records"][0])
    record.pop("selection_index")
    record[field] = invalid_value
    with pytest.raises(TomeV3ValidationError, match="malformed_schema"):
        normalize_semantic_record(record)


@pytest.mark.parametrize("invalid_name", ["bad space.txt", "bad:colon.txt", ".hidden"])
def test_pc06_member_path_grammar_rejects_disallowed_public_names(
    tmp_path: Path, invalid_name: str
) -> None:
    """PC06: discovery applies the published member-path grammar, not just safety."""

    artifact = _valid_artifact(tmp_path / "artifact")
    _write(artifact, invalid_name, b"unclassified")
    with pytest.raises(TomeV3ValidationError, match="undeclared_member"):
        validate_tome_artifact_v3(artifact)


def test_pc06_duplicate_rtome_member_is_rejected_before_extraction(
    tmp_path: Path,
) -> None:
    """PC06: archive member uniqueness applies to ``.rtome`` transports too."""

    artifact = _valid_artifact(tmp_path / "directory")
    archive_path = tmp_path / "duplicate.rtome"
    with tarfile.open(archive_path, "w:gz") as archive:
        for member in sorted(artifact.rglob("*")):
            if member.is_file():
                archive.add(member, arcname=member.relative_to(artifact).as_posix())
        duplicate = artifact / "cover_page.json"
        duplicate_info = tarfile.TarInfo("cover_page.json")
        duplicate_info.size = duplicate.stat().st_size
        archive.addfile(duplicate_info, io.BytesIO(duplicate.read_bytes()))
    with pytest.raises(TomeV3ValidationError, match="undeclared_member"):
        validate_tome_artifact_v3(archive_path)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("classification", "not_a_v3_classification"),
        ("required_for_standard_validation", "true"),
        ("required_for_standard_validation", 1),
    ],
)
def test_inventory_row_closed_types_are_enforced_after_receipts_are_refreshed(
    tmp_path: Path, field: str, invalid_value: object
) -> None:
    """Inventory classification/flag are validation inputs, never descriptive hints."""

    artifact = _valid_artifact(tmp_path / "artifact")

    def mutate(rows: list[dict[str, object]]) -> None:
        rows[0][field] = invalid_value

    _rewrite_inventory_and_cover(artifact, mutate)
    with pytest.raises(TomeV3ValidationError, match="incoherent_package_graph"):
        validate_tome_artifact_v3(artifact)


@pytest.mark.parametrize("case_id", ["PC01", "PC02", "PC03", "PC05", "PC10", "PC12"])
def test_raw_shard_receipt_cases_fail_before_semantic_consumption(
    tmp_path: Path, case_id: str
) -> None:
    """The physical shard mutations in these PC cases share one raw receipt guard."""

    artifact = _valid_artifact(tmp_path / case_id)
    shard = artifact / "selected_exemplars/shards/shard-00000.jsonl"
    original = shard.read_bytes()
    if case_id == "PC01":
        mutated = bytes([original[0] ^ 1]) + original[1:]
    elif case_id == "PC02":
        mutated = original[:-1]
    elif case_id == "PC03":
        mutated = original + b"x"
    elif case_id == "PC05":
        mutated = b"{}\n"
    elif case_id == "PC10":
        mutated = b""
    else:
        mutated = original.replace(b"example-a", b"example-z")
    shard.write_bytes(mutated)
    with pytest.raises(TomeV3ValidationError, match="corrupt_shard"):
        validate_tome_artifact_v3(artifact)


@pytest.mark.parametrize(
    ("case_id", "member", "expected"),
    [
        ("PC04", "selected_exemplars/shards/shard-00000.jsonl", "missing_member"),
        ("PC07", "provenance/behavioral-policy.json", "missing_member"),
    ],
)
def test_pc04_and_pc07_missing_inventoried_members_fail_closed(
    tmp_path: Path, case_id: str, member: str, expected: str
) -> None:
    artifact = _valid_artifact(tmp_path / case_id)
    (artifact / member).unlink()
    with pytest.raises(TomeV3ValidationError, match=expected) as error:
        validate_tome_artifact_v3(artifact)
    assert error.value.issue.phase in {1, 3}


def test_pc06_allowed_extra_member_is_not_silently_nonpublic(tmp_path: Path) -> None:
    artifact = _valid_artifact(tmp_path / "PC06")
    _write(artifact, "diagnostics/extra.json", b"{}")
    with pytest.raises(TomeV3ValidationError, match="undeclared_member"):
        validate_tome_artifact_v3(artifact)


def test_public_package_rejects_an_inventoried_private_journal(tmp_path: Path) -> None:
    """A private journal cannot become public by assigning it a known role."""

    artifact = _valid_artifact(tmp_path / "private-journal")
    journal_path = "private/journal.json"
    journal_raw = b"{}"
    _write(artifact, journal_path, journal_raw)

    def mutate(rows: list[dict[str, object]]) -> None:
        rows.append(
            {
                "path": journal_path,
                "sha256": _digest(journal_raw),
                "size_bytes": len(journal_raw),
                "member_role": "payload_shard",
                "classification": "operational",
                "required_for_standard_validation": True,
            }
        )

    _rewrite_inventory_and_cover(artifact, mutate)
    with pytest.raises(TomeV3ValidationError, match="incoherent_package_graph"):
        validate_tome_artifact_v3(artifact)


def test_pc08_pc09_and_pc13_index_coverage_and_location_are_closed(
    tmp_path: Path,
) -> None:
    artifact = _valid_artifact(tmp_path / "PC08")
    record = json.loads(
        (artifact / "selected_exemplars/shards/shard-00000.jsonl").read_text()
    )
    _rebuild_from_records(artifact, [record, deepcopy(record)], [1, 1])
    with pytest.raises(TomeV3ValidationError, match="index_incoherent"):
        validate_tome_artifact_v3(artifact)  # PC08: coherent receipts, duplicate ID.

    artifact = _two_record_artifact(tmp_path / "PC09")
    payload_path = "selected_exemplars/payload-index.jsonl"
    rows = (artifact / payload_path).read_bytes().splitlines(keepends=True)
    _write(artifact, payload_path, rows[:1][0])
    _refresh_complete_public_graph(artifact)
    with pytest.raises(TomeV3ValidationError, match="index_incoherent"):
        validate_tome_artifact_v3(artifact)  # PC09.

    artifact = _two_record_artifact(tmp_path / "PC13")
    rows = [
        json.loads(line) for line in (artifact / payload_path).read_text().splitlines()
    ]
    rows[1]["shard_id"] = 0
    rows[1]["row"] = 0
    _write(artifact, payload_path, b"".join(_raw(row, jsonl=True) for row in rows))
    _refresh_complete_public_graph(artifact)
    with pytest.raises(TomeV3ValidationError, match="index_incoherent"):
        validate_tome_artifact_v3(artifact)  # PC13.


def test_pc11_reordered_coherent_layout_still_requires_declared_sequence(
    tmp_path: Path,
) -> None:
    artifact = _two_record_artifact(tmp_path / "PC11", shard_sizes=[2])
    original_identity = (artifact / "provenance/semantic-identity.json").read_bytes()
    records = [
        json.loads(line)
        for line in (artifact / "selected_exemplars/shards/shard-00000.jsonl")
        .read_text()
        .splitlines()
    ]
    _rebuild_from_records(artifact, list(reversed(records)), [2])
    _write(artifact, "provenance/semantic-identity.json", original_identity)
    _refresh_complete_public_graph(artifact)
    with pytest.raises(TomeV3ValidationError, match="semantic_sequence_mismatch"):
        validate_tome_artifact_v3(artifact)


@pytest.mark.parametrize("case_id", ["PC17", "PC18", "PC22", "PC23", "PC27"])
def test_pc17_pc18_pc22_pc23_pc27_closed_declared_bindings(
    tmp_path: Path, case_id: str
) -> None:
    artifact = _two_record_artifact(tmp_path / case_id)
    if case_id == "PC17":
        cover = json.loads((artifact / "cover_page.json").read_text())
        cover["record_count"] = 99
        _write(artifact, "cover_page.json", _raw(cover))
        expected = "index_incoherent"
    elif case_id == "PC18":
        path = "selected_exemplars/payload-shards.jsonl"
        rows = [json.loads(line) for line in (artifact / path).read_text().splitlines()]
        rows[1]["first_selection_index"] = 99
        _write(artifact, path, b"".join(_raw(row, jsonl=True) for row in rows))
        _refresh_complete_public_graph(artifact)
        expected = "index_incoherent"
    elif case_id == "PC22":
        cover = json.loads((artifact / "cover_page.json").read_text())
        cover["schema_version"] = "unsupported"
        _write(artifact, "cover_page.json", _raw(cover))
        expected = "unsupported_version"
    elif case_id == "PC23":
        caps_path = "provenance/capabilities.json"
        caps = json.loads((artifact / caps_path).read_text())
        caps["required"] = ["standard_integrity_v3"]
        _write(artifact, caps_path, _raw(caps))
        _refresh_complete_public_graph(artifact)
        expected = "incoherent_package_graph"
    else:
        path = "provenance/semantic-identity.json"
        identity = json.loads((artifact / path).read_text())
        identity["semantic_root"] = "sha256:" + "0" * 64
        _write(artifact, path, _raw(identity))
        _refresh_complete_public_graph(artifact)
        expected = "semantic_root_mismatch"
    with pytest.raises(TomeV3ValidationError, match=expected):
        validate_tome_artifact_v3(artifact)


@pytest.mark.parametrize("case_id", ["PC14", "PC15", "PC16", "PC19"])
def test_pc14_pc15_pc16_pc19_stale_or_wrong_references_fail_closed(
    tmp_path: Path, case_id: str
) -> None:
    artifact = _two_record_artifact(tmp_path / case_id)
    if case_id == "PC14":
        path = "selected_exemplars/payload-shards.jsonl"
        rows = [json.loads(line) for line in (artifact / path).read_text().splitlines()]
        rows[1]["sha256"] = "sha256:" + "0" * 64
        _write(artifact, path, b"".join(_raw(row, jsonl=True) for row in rows))
        _refresh_complete_public_graph(artifact)
        expected = "corrupt_shard"
    elif case_id == "PC15":
        cover = json.loads((artifact / "cover_page.json").read_text())
        cover["manifest_header_ref"]["path"] = "manifests/nope.json"
        _write(artifact, "cover_page.json", _raw(cover))
        expected = "incoherent_package_graph"
    elif case_id == "PC16":
        path = "manifests/content-manifest-header.json"
        header = json.loads((artifact / path).read_text())
        header["inventory_ref"]["path"] = "manifests/nope.jsonl"
        _write(artifact, path, _raw(header))
        cover = json.loads((artifact / "cover_page.json").read_text())
        cover["manifest_header_ref"] = _ref(
            path, _raw(header), "tome_content_manifest_header_v4"
        )
        _write(artifact, "cover_page.json", _raw(cover))
        expected = "incoherent_package_graph"
    else:
        path = "selected_exemplars/layout.json"
        layout = json.loads((artifact / path).read_text())
        layout["payload_index_ref"]["schema_version"] = "wrong"
        _write(artifact, path, _raw(layout))
        _refresh_complete_public_graph(artifact)
        expected = "malformed_reference"
    with pytest.raises(TomeV3ValidationError, match=expected):
        validate_tome_artifact_v3(artifact)


@pytest.mark.parametrize("case_id", ["PC20", "PC21"])
def test_parser_and_dispatch_conformance_cases(case_id: str) -> None:
    """Strict parse/dispatch primitives exercise the named PC boundaries."""

    if case_id == "PC20":
        from radjax_contract.tome.v3.strict_json import loads

        with pytest.raises(TomeV3ValidationError, match="malformed_schema"):
            loads('{"a":1,"a":2}')
    elif case_id == "PC21":
        from radjax_contract.tome.v3.strict_json import load_jsonl

        with pytest.raises(TomeV3ValidationError, match="malformed_jsonl"):
            load_jsonl(b"{}\r\n")


def test_pc48_to_pc50_external_archive_receipt_is_closed_and_references_are_opaque(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "artifact.rto"
    archive.write_bytes(b"test transport bytes")
    receipt = {
        "schema_version": "radjax_tome_archive_receipt_v1",
        "algorithm_id": "sha256",
        "archive_sha256": _digest(archive.read_bytes()),
        "archive_size_bytes": archive.stat().st_size,
        "transport": "rtome",
        "artifact_reference": "release/test",
    }
    path = tmp_path / "receipt.json"
    path.write_bytes(_raw(receipt))
    assert validate_archive_receipt_v3(archive, path).matches  # PC48
    receipt["artifact_reference"] = "bad\nreference"
    path.write_bytes(_raw(receipt))
    with pytest.raises(TomeV3ValidationError, match="malformed_reference"):
        validate_archive_receipt_v3(archive, path)  # PC49
    receipt["artifact_reference"] = "release/test"
    receipt["unexpected"] = True
    path.write_bytes(_raw(receipt))
    with pytest.raises(TomeV3ValidationError, match="malformed_schema"):
        validate_archive_receipt_v3(archive, path)  # PC50


@pytest.mark.parametrize(
    ("case_id", "mutate", "expected"),
    [
        (
            "PC52",
            lambda a: a.__setitem__("envelope", "%%%"),
            "attestation_envelope_invalid",
        ),
        (
            "PC53",
            lambda a: a.__setitem__("envelope", canonical_base64_encode(b"wrong")),
            "attestation_binding_mismatch",
        ),
        (
            "PC54",
            lambda a: a.__setitem__("envelope_algorithm_id", "unknown_v1"),
            "attestation_algorithm_unsupported",
        ),
    ],
)
def test_pc51_to_pc54_attestation_envelope_is_external_and_exact(
    tmp_path: Path,
    case_id: str,
    mutate: Callable[[dict[str, object]], None],
    expected: str,
) -> None:
    artifact = _valid_artifact(tmp_path / "artifact")
    identity = json.loads((artifact / "provenance/semantic-identity.json").read_text())
    attestation: dict[str, object] = {
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
    attestation["envelope"] = canonical_base64_encode(
        fv3({key: attestation[key] for key in sorted(attestation, key=str.encode)})
    )
    mutate(attestation)
    path = tmp_path / f"{case_id}.json"
    path.write_bytes(_raw(attestation))
    with pytest.raises(TomeV3ValidationError, match=expected):
        verify_external_tome_attestation_v3(
            artifact,
            path,
            requirement=AttestationRequirement.REQUIRED,
            evaluation_time_utc=datetime(2026, 8, 6, tzinfo=UTC),
        )


def test_pc55_package_local_evidence_never_satisfies_external_attestation(
    tmp_path: Path,
) -> None:
    artifact = _valid_artifact(tmp_path / "PC55")
    with pytest.raises(TomeV3ValidationError, match="attestation_not_external"):
        verify_external_tome_attestation_v3(
            artifact,
            artifact / "provenance/semantic-identity.json",
            requirement=AttestationRequirement.REQUIRED,
            evaluation_time_utc=datetime(2026, 8, 6, tzinfo=UTC),
        )


def test_pc56_pc57_historical_dispatch_remains_native_and_separate(
    tmp_path: Path,
) -> None:
    """v3 imports neither normalize nor replace the frozen v1/v2 validators."""

    from test_student_consumption_v2 import _v2_artifact
    from test_tome_contract_publication import _student_artifact

    from radjax_contract.tome import validate_and_resolve_student_consumption

    v1 = validate_and_resolve_student_consumption(
        _student_artifact(tmp_path / "PC56"), profile_id="native_v3_student_v1"
    )
    assert v1.ok, v1.issues
    v2 = validate_and_resolve_student_consumption(
        _v2_artifact(tmp_path / "PC57"), profile_id="native_v3_student_v2"
    )
    assert v2.ok, v2.issues


def _governed_input(identity: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "radjax_tome_governed_comparison_v1",
        "expected_semantic_root": identity["semantic_root"],
        "expected_authority_identity": identity["semantic_authority_identity"],
        "expected_contract_version": identity["contract_version"],
        "expected_profile_id": identity["semantic_profile_id"],
        "expected_policy_identity": identity["behavioral_policy_identity"],
    }


def _external_attestation(identity: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {
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
    result["envelope"] = canonical_base64_encode(
        fv3({key: result[key] for key in sorted(result, key=str.encode)})
    )
    return result


def test_pc24_to_pc27_governed_identity_bindings_are_independent(
    tmp_path: Path,
) -> None:
    artifact = _valid_artifact(tmp_path / "PC24")
    authority_path = "provenance/semantic-authority.json"
    authority = json.loads((artifact / authority_path).read_text())
    authority["entries"][0]["identity"] = "sha256:" + "9" * 64
    _write(artifact, authority_path, _raw(authority))
    _refresh_complete_public_graph(artifact)
    with pytest.raises(TomeV3ValidationError, match="authority_mismatch"):
        validate_tome_artifact_v3(artifact)

    artifact = _valid_artifact(tmp_path / "PC26")
    policy_path = "provenance/behavioral-policy.json"
    policy = json.loads((artifact / policy_path).read_text())
    policy["selection_policy"] = "other_governed_policy"
    _write(artifact, policy_path, _raw(policy))
    _refresh_complete_public_graph(artifact)
    with pytest.raises(TomeV3ValidationError, match="policy_mismatch"):
        validate_tome_artifact_v3(artifact)

    artifact = _valid_artifact(tmp_path / "PC25")
    identity_path = "provenance/semantic-identity.json"
    identity = json.loads((artifact / identity_path).read_text())
    identity["contract_version"] = "radjax_tome_artifact_contract@3.0.1"
    _write(artifact, identity_path, _raw(identity))
    _refresh_complete_public_graph(artifact)
    with pytest.raises(TomeV3ValidationError, match="semantic_root_mismatch"):
        validate_tome_artifact_v3(artifact)


def test_pc28_pc29_resharding_and_transport_do_not_change_semantic_identity(
    tmp_path: Path,
) -> None:
    artifact = _two_record_artifact(tmp_path / "directory", shard_sizes=[1, 1])
    before = validate_tome_artifact_v3(artifact).semantic_root
    records = [
        json.loads(path.read_text())
        for path in sorted((artifact / "selected_exemplars/shards").glob("*.jsonl"))
    ]
    _rebuild_from_records(artifact, records, [2])
    assert validate_tome_artifact_v3(artifact).semantic_root == before  # PC28

    cover = json.loads((artifact / "cover_page.json").read_text())
    cover["package"]["transport"] = "rtome"
    _write(artifact, "cover_page.json", _raw(cover))
    archive = tmp_path / ("repacked.rtom" + "e")
    with tarfile.open(archive, "w:gz") as tar:
        for member in sorted(artifact.rglob("*"), reverse=True):
            if member.is_file():
                tar.add(member, arcname=member.relative_to(artifact).as_posix())
    assert validate_tome_artifact_v3(archive).semantic_root == before  # PC29


def test_pc33_pc34_streaming_verifies_each_shard_before_yield(tmp_path: Path) -> None:
    artifact = _valid_artifact(tmp_path / "PC33")
    shard = artifact / "selected_exemplars/shards/shard-00000.jsonl"
    shard.write_bytes(shard.read_bytes() + b"x")
    with open_tome_artifact_v3(artifact) as reader:
        iterator = iter(reader)
        with pytest.raises(TomeV3ValidationError, match="corrupt_shard"):
            next(iterator)  # PC33: no first-shard row escapes.

    artifact = _two_record_artifact(tmp_path / "PC34")
    shard = artifact / "selected_exemplars/shards/shard-00001.jsonl"
    shard.write_bytes(shard.read_bytes() + b"x")
    with open_tome_artifact_v3(artifact) as reader:
        iterator = iter(reader)
        assert next(iterator)["selected_example_id"] == "example-a"
        with pytest.raises(TomeV3ValidationError, match="corrupt_shard"):
            next(iterator)  # PC34: no later corrupt-shard row escapes.


def test_pc30_to_pc32_self_consistency_and_external_expectations(
    tmp_path: Path,
) -> None:
    artifact = _two_record_artifact(tmp_path / "PC30")
    original_identity = json.loads(
        (artifact / "provenance/semantic-identity.json").read_text()
    )
    records = [
        json.loads(path.read_text())
        for path in sorted((artifact / "selected_exemplars/shards").glob("*.jsonl"))
    ]
    records[0]["top_token_ids"][0] = 1
    records[0]["source_top_token_id"] = 1
    _rebuild_from_records(artifact, records, [1, 1])
    changed = validate_tome_artifact_v3(artifact)  # PC30: no external expected root.
    assert changed.semantic_root != original_identity["semantic_root"]

    governed = tmp_path / "governed.json"
    governed.write_bytes(_raw(_governed_input(original_identity)))
    with pytest.raises(TomeV3ValidationError, match="governed_expected_root_mismatch"):
        compare_governed_tome_artifact_v3(artifact, governed)  # PC31.

    attestation = tmp_path / "attestation.json"
    attestation.write_bytes(_raw(_external_attestation(original_identity)))
    with pytest.raises(TomeV3ValidationError, match="attestation_binding_mismatch"):
        verify_external_tome_attestation_v3(
            artifact,
            attestation,
            requirement=AttestationRequirement.REQUIRED,
            evaluation_time_utc=datetime(2026, 8, 6, tzinfo=UTC),
        )  # PC32.
