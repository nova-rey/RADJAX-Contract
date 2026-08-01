"""Focused public-boundary regressions for the explicit v4 profile."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

from test_student_consumption_v2 import _sha256, _v2_artifact

from radjax_contract.tome import validate_and_resolve_student_consumption
from radjax_contract.tome.student_consumption_v2 import resource_semantic_digest
from radjax_contract.tome.student_consumption_v4 import (
    _identity_digest,
    _sha256_syntax,
)

_PROVENANCE_ONLY_ROLES = {"delivery_receipt", "authority_reference"}


def _sync_v4_identity(manifest: dict[str, object]) -> None:
    """Refresh only the v4 batch-semantic projection."""

    identity = manifest["semantic_identity"]
    assert isinstance(identity, dict)
    resources = manifest["resources"]
    assert isinstance(resources, list)
    identity["resources"] = [
        {
            key: row[key]
            for key in ("resource_id", "role", "instance_id", "semantic_digest")
        }
        for row in resources
        if isinstance(row, dict) and row["role"] not in _PROVENANCE_ONLY_ROLES
    ]
    identity["semantic_digest"] = _identity_digest(identity)


def _v4_artifact(root: Path) -> Path:
    """Lift a real v2 test artifact into the explicitly new v4 family."""

    root = _v2_artifact(root)
    v2_path = root / "manifests/student_consumption_v2.json"
    manifest = json.loads(v2_path.read_text(encoding="utf-8"))
    sidecars = {
        "row_range_declaration": {
            "schema_version": "native_v3_student_consumption_row_ranges_v1",
            "example_count": 1,
            "assignment_count": 2,
            "ordering": "example_index_then_source_position",
        },
        "delivery_receipt": {
            "schema_version": "native_v3_student_consumption_delivery_receipt_v2",
            "delivery_path": "two_pass_rerun_selected",
            "assignment_encoding": "npz_named_arrays_v1",
            "statistics_encoding": "npz_named_arrays_v1",
            "source_roles": [
                "native_v3_mode_assignments",
                "native_v3_score_shards",
            ],
        },
        "authority_reference": {
            "schema_version": "native_v3_student_consumption_authority_reference_v1",
            "selection_integration_config_hash": "sha256:" + "e" * 64,
            "score_pass_authority_hash": "sha256:" + "f" * 64,
        },
    }
    for row in manifest["resources"]:
        if row["role"] not in sidecars:
            continue
        path = root / row["inventory_binding"]
        path.write_text(
            json.dumps(sidecars[row["role"]], sort_keys=True), encoding="utf-8"
        )
        row["semantic_digest"] = resource_semantic_digest(
            path, row["encoding"], row["consumption"]
        )
    identity = manifest["semantic_identity"]
    identity["schema_version"] = "radjax_tome_student_consumption_semantic_identity_v4"
    identity["profile_id"] = "native_v3_student_v4"
    _sync_v4_identity(manifest)
    manifest["schema_version"] = "radjax_tome_student_consumption_manifest_v4"
    manifest["profile_id"] = "native_v3_student_v4"
    v3_path = root / "manifests/student_consumption_v4.json"
    v3_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    cover_path = root / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    inventory = cover["manifests"]["content"]["inventory"]
    inventory[:] = [
        row
        for row in inventory
        if row["path"] != "manifests/student_consumption_v2.json"
    ]
    for row in manifest["resources"]:
        entry = next(
            item for item in inventory if item["path"] == row["inventory_binding"]
        )
        path = root / row["inventory_binding"]
        entry["sha256"], entry["size_bytes"] = _sha256(path), path.stat().st_size
    inventory.append(
        {
            "path": "manifests/student_consumption_v4.json",
            "sha256": _sha256(v3_path),
            "size_bytes": v3_path.stat().st_size,
            "classification": "manifest",
            "training_authoritative": False,
        }
    )
    cover["schema_version"] = "radjax_tome_cover_v3_student_consumption_v4"
    cover["student_consumption"] = {
        "profile_id": "native_v3_student_v4",
        "manifest_path": "manifests/student_consumption_v4.json",
        "manifest_sha256": _sha256(v3_path),
        "semantic_digest": identity["semantic_digest"],
        "digest_method": "sha256",
        "required_capabilities": [],
    }
    cover_path.write_text(json.dumps(cover, sort_keys=True), encoding="utf-8")
    return root


def _refresh_v4_integrity(root: Path, manifest: dict[str, object]) -> None:
    """Refresh raw and consumption identity after an adversarial mutation."""

    manifest_path = root / "manifests/student_consumption_v4.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    cover_path = root / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    inventory = cover["manifests"]["content"]["inventory"]
    for row in manifest["resources"]:
        entry = next(
            item for item in inventory if item["path"] == row["inventory_binding"]
        )
        path = root / row["inventory_binding"]
        entry["sha256"], entry["size_bytes"] = _sha256(path), path.stat().st_size
    manifest_entry = next(
        item
        for item in inventory
        if item["path"] == "manifests/student_consumption_v4.json"
    )
    manifest_entry["sha256"], manifest_entry["size_bytes"] = (
        _sha256(manifest_path),
        manifest_path.stat().st_size,
    )
    cover["student_consumption"]["manifest_sha256"] = _sha256(manifest_path)
    cover["student_consumption"]["semantic_digest"] = manifest["semantic_identity"][
        "semantic_digest"
    ]
    cover_path.write_text(json.dumps(cover, sort_keys=True), encoding="utf-8")


def test_v2_artifact_remains_valid_only_under_its_explicit_profile(
    tmp_path: Path,
) -> None:
    artifact = _v2_artifact(tmp_path)

    v2 = validate_and_resolve_student_consumption(
        artifact, profile_id="native_v3_student_v2"
    )
    v4 = validate_and_resolve_student_consumption(
        artifact, profile_id="native_v3_student_v4"
    )

    assert v2.ok, v2.issues
    assert not v4.ok
    assert [issue.code for issue in v4.issues] == ["TSC002_COVER_VERSION_UNSUPPORTED"]
    assert v4.descriptor is None


def test_v4_artifact_is_never_reinterpreted_as_v2(tmp_path: Path) -> None:
    artifact = _v4_artifact(tmp_path)
    result = validate_and_resolve_student_consumption(
        artifact, profile_id="native_v3_student_v2"
    )
    assert [issue.code for issue in result.issues] == [
        "TSC002_COVER_VERSION_UNSUPPORTED"
    ]


def test_v4_archive_delivery_preserves_the_explicit_tgz_contract(
    tmp_path: Path,
) -> None:
    """The v4-to-v2 compatibility adapter must not reject its own staging dir."""

    directory = _v4_artifact(tmp_path / "directory")
    cover_path = directory / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    cover["package"]["transport"] = "tgz"
    cover_path.write_text(json.dumps(cover, sort_keys=True), encoding="utf-8")
    archive = tmp_path / "student.tgz"
    with tarfile.open(archive, "w:gz") as handle:
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            handle.add(path, arcname=path.relative_to(directory).as_posix())
    result = validate_and_resolve_student_consumption(
        archive, profile_id="native_v3_student_v4"
    )
    assert result.ok, result.issues


def test_v4_authority_hash_requires_exact_lowercase_sha256_syntax() -> None:
    assert _sha256_syntax("sha256:" + "a" * 64)
    assert not _sha256_syntax("sha256:" + "A" * 64)
    assert not _sha256_syntax("sha256:" + "g" * 64)
    assert not _sha256_syntax("sha256:" + "a" * 63)


def test_v4_admits_declared_evidence_and_rejects_authority_mismatch(
    tmp_path: Path,
) -> None:
    artifact = _v4_artifact(tmp_path)
    admitted = validate_and_resolve_student_consumption(
        artifact, profile_id="native_v3_student_v4", strict=True
    )
    assert admitted.ok, admitted.issues
    assert admitted.descriptor is not None
    assert (
        admitted.descriptor.schema_version == "radjax_student_consumption_descriptor_v4"
    )

    authority = artifact / "resources/09.json"
    payload = json.loads(authority.read_text(encoding="utf-8"))
    payload["selection_integration_config_hash"] = "sha256:" + "0" * 64
    authority.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    # Refresh the derived resource and profile identity as a malicious but
    # self-consistent producer could; v4 must still catch the base-authority
    # contradiction rather than accepting raw integrity alone.
    manifest_path = artifact / "manifests/student_consumption_v4.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = next(
        item for item in manifest["resources"] if item["role"] == "authority_reference"
    )
    row["semantic_digest"] = resource_semantic_digest(
        authority, row["encoding"], row["consumption"]
    )
    _sync_v4_identity(manifest)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    entry = next(
        item
        for item in cover["manifests"]["content"]["inventory"]
        if item["path"] == "resources/09.json"
    )
    entry["sha256"], entry["size_bytes"] = _sha256(authority), authority.stat().st_size
    manifest_entry = next(
        item
        for item in cover["manifests"]["content"]["inventory"]
        if item["path"] == "manifests/student_consumption_v4.json"
    )
    manifest_entry["sha256"], manifest_entry["size_bytes"] = (
        _sha256(manifest_path),
        manifest_path.stat().st_size,
    )
    cover["student_consumption"]["manifest_sha256"] = _sha256(manifest_path)
    cover["student_consumption"]["semantic_digest"] = manifest["semantic_identity"][
        "semantic_digest"
    ]
    cover_path.write_text(json.dumps(cover, sort_keys=True), encoding="utf-8")
    rejected = validate_and_resolve_student_consumption(
        artifact, profile_id="native_v3_student_v4"
    )
    assert [issue.code for issue in rejected.issues] == [
        "TSC072_AUTHORITY_REFERENCE_MISMATCH"
    ]


def test_v4_path_a_and_path_b_provenance_share_batch_semantic_identity(
    tmp_path: Path,
) -> None:
    """Delivery evidence is validated but cannot redefine batch meaning."""

    path_a = _v4_artifact(tmp_path / "path-a")
    path_b = _v4_artifact(tmp_path / "path-b")
    manifest_path = path_b / "manifests/student_consumption_v4.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = path_b / "resources/08.json"
    body = json.loads(receipt.read_text(encoding="utf-8"))
    body["delivery_path"] = "one_pass_full"
    receipt.write_text(json.dumps(body, sort_keys=True), encoding="utf-8")
    row = next(
        item for item in manifest["resources"] if item["role"] == "delivery_receipt"
    )
    row["semantic_digest"] = resource_semantic_digest(
        receipt, row["encoding"], row["consumption"]
    )
    digest_before = manifest["semantic_identity"]["semantic_digest"]
    _sync_v4_identity(manifest)
    assert manifest["semantic_identity"]["semantic_digest"] == digest_before
    _refresh_v4_integrity(path_b, manifest)

    result_a = validate_and_resolve_student_consumption(
        path_a, profile_id="native_v3_student_v4", strict=True
    )
    result_b = validate_and_resolve_student_consumption(
        path_b, profile_id="native_v3_student_v4", strict=True
    )
    assert result_a.ok, result_a.issues
    assert result_b.ok, result_b.issues
    assert result_a.descriptor is not None and result_b.descriptor is not None
    assert (
        result_a.descriptor.consumption_semantic_digest
        == result_b.descriptor.consumption_semantic_digest
    )
    assert (
        json.loads((path_a / "resources/08.json").read_text(encoding="utf-8"))[
            "delivery_path"
        ]
        != body["delivery_path"]
    )


def test_v4_rejects_self_consistent_row_range_and_delivery_mutations(
    tmp_path: Path,
) -> None:
    artifact = _v4_artifact(tmp_path / "ranges")
    manifest_path = artifact / "manifests/student_consumption_v4.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ranges = artifact / "resources/07.json"
    range_body = json.loads(ranges.read_text(encoding="utf-8"))
    range_body["assignment_count"] = 3
    ranges.write_text(json.dumps(range_body, sort_keys=True), encoding="utf-8")
    row = next(
        item
        for item in manifest["resources"]
        if item["role"] == "row_range_declaration"
    )
    row["semantic_digest"] = resource_semantic_digest(
        ranges, row["encoding"], row["consumption"]
    )
    _sync_v4_identity(manifest)
    _refresh_v4_integrity(artifact, manifest)
    result = validate_and_resolve_student_consumption(
        artifact, profile_id="native_v3_student_v4"
    )
    assert [issue.code for issue in result.issues] == [
        "TSC070_ROW_RANGE_DECLARATION_INVALID"
    ]

    artifact = _v4_artifact(tmp_path / "receipt")
    manifest_path = artifact / "manifests/student_consumption_v4.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = artifact / "resources/08.json"
    receipt_body = json.loads(receipt.read_text(encoding="utf-8"))
    receipt_body["delivery_path"] = "unknown"
    receipt.write_text(json.dumps(receipt_body, sort_keys=True), encoding="utf-8")
    row = next(
        item for item in manifest["resources"] if item["role"] == "delivery_receipt"
    )
    row["semantic_digest"] = resource_semantic_digest(
        receipt, row["encoding"], row["consumption"]
    )
    _sync_v4_identity(manifest)
    _refresh_v4_integrity(artifact, manifest)
    result = validate_and_resolve_student_consumption(
        artifact, profile_id="native_v3_student_v4"
    )
    assert [issue.code for issue in result.issues] == [
        "TSC071_DELIVERY_RECEIPT_INVALID"
    ]
