"""Focused regressions for the additive derived-sidecar consumption profile."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from test_tome_contract_publication import _sha256, _student_artifact

from radjax_contract.tome import (
    open_verified_student_resource,
    validate_and_resolve_student_consumption,
)
from radjax_contract.tome.student_consumption_v2 import resource_semantic_digest


def _canonical_identity(identity: dict[str, object]) -> str:
    projection = {
        key: value for key, value in identity.items() if key != "semantic_digest"
    }
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def _rewrite_manifest_inventory(root: Path, manifest: dict[str, object]) -> None:
    manifest_path = root / "manifests/student_consumption_v2.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    cover_path = root / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    inventory = cover["manifests"]["content"]["inventory"]
    inventory[:] = [
        item
        for item in inventory
        if item["path"]
        not in {
            "manifests/student_consumption_v1.json",
            "manifests/student_consumption_v2.json",
        }
    ]
    for row in manifest["resources"]:
        path = root / row["inventory_binding"]
        entry = next(
            item for item in inventory if item["path"] == row["inventory_binding"]
        )
        entry["sha256"], entry["size_bytes"] = _sha256(path), path.stat().st_size
    inventory.append(
        {
            "path": "manifests/student_consumption_v2.json",
            "sha256": _sha256(manifest_path),
            "size_bytes": manifest_path.stat().st_size,
            "classification": "manifest",
            "training_authoritative": False,
        }
    )
    identity = manifest["semantic_identity"]
    cover["schema_version"] = "radjax_tome_cover_v3_student_consumption_v2"
    cover["student_consumption"] = {
        "profile_id": "native_v3_student_v2",
        "manifest_path": "manifests/student_consumption_v2.json",
        "manifest_sha256": _sha256(manifest_path),
        "semantic_digest": identity["semantic_digest"],
    }
    cover_path.write_text(json.dumps(cover, sort_keys=True), encoding="utf-8")


def _refresh_consumption_identity(manifest: dict[str, object]) -> None:
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
        if isinstance(row, dict)
    ]
    identity["semantic_digest"] = _canonical_identity(identity)


def _v2_artifact(root: Path) -> Path:
    root = _student_artifact(root)
    old = json.loads((root / "manifests/student_consumption_v1.json").read_text())
    resources = []
    for row in old["resources"]:
        resource = {
            key: value
            for key, value in row.items()
            if key != "training_payload_binding"
        }
        if resource["encoding"] == "npz":
            with np.load(
                root / resource["inventory_binding"], allow_pickle=False
            ) as archive:
                axes_by_role = {
                    "target_shard": {
                        "input_ids": ["example", "token_position"],
                        "attention_mask": ["example", "token_position"],
                        "corridor_lengths": ["example"],
                    },
                    "corridor_assignment": {
                        "position_example_index": ["assignment"],
                        "position": ["assignment"],
                        "mode_id": ["assignment"],
                        "weight": ["assignment"],
                    },
                    "corridor_observed_statistics": {
                        name: ["assignment"] for name in archive.files
                    },
                }
                resource["consumption"] = {
                    **resource["consumption"],
                    "axes": axes_by_role[resource["role"]],
                }
        resource["semantic_digest"] = resource_semantic_digest(
            root / resource["inventory_binding"],
            resource["encoding"],
            resource["consumption"],
        )
        resources.append(resource)
    identity = old["semantic_identity"]
    identity.update(
        {
            "schema_version": "radjax_tome_student_consumption_semantic_identity_v2",
            "profile_id": "native_v3_student_v2",
            "resources": [
                {
                    key: row[key]
                    for key in ("resource_id", "role", "instance_id", "semantic_digest")
                }
                for row in resources
            ],
        }
    )
    identity["semantic_digest"] = _canonical_identity(identity)
    manifest = {
        "schema_version": "radjax_tome_student_consumption_manifest_v2",
        "profile_id": "native_v3_student_v2",
        "base_artifact_semantic_digest": old["base_artifact_semantic_digest"],
        "semantic_identity": identity,
        "resources": resources,
        "joins": old["joins"],
        "provenance": {
            "derivation": "independently_semantically_digested_derived_sidecars"
        },
    }
    _rewrite_manifest_inventory(root, manifest)
    return root


def test_v2_accepts_independently_digested_resources_without_training_binding(
    tmp_path: Path,
) -> None:
    artifact = _v2_artifact(tmp_path)
    result = validate_and_resolve_student_consumption(
        artifact, profile_id="native_v3_student_v2"
    )
    assert result.ok, result.issues
    assert result.descriptor is not None
    assert (
        result.descriptor.schema_version == "radjax_student_consumption_descriptor_v2"
    )
    assert not hasattr(
        result.descriptor.corridor_resources[0], "training_payload_binding"
    )
    with open_verified_student_resource(
        artifact, "target_shard/default", profile_id="native_v3_student_v2"
    ) as handle:
        assert handle.read(2) == b"PK"


def test_v2_rejects_derived_resource_semantic_mutation_even_after_raw_inventory_refresh(
    tmp_path: Path,
) -> None:
    artifact = _v2_artifact(tmp_path)
    target = artifact / "resources/00.npz"
    np.savez(
        target,
        input_ids=np.array([[2, 1]], dtype=np.int32),
        attention_mask=np.array([[1, 1]], dtype=np.int32),
        corridor_lengths=np.array([2], dtype=np.int32),
    )
    manifest = json.loads(
        (artifact / "manifests/student_consumption_v2.json").read_text()
    )
    _rewrite_manifest_inventory(artifact, manifest)
    result = validate_and_resolve_student_consumption(
        artifact, profile_id="native_v3_student_v2"
    )
    assert [issue.code for issue in result.issues] == [
        "TSC015_DERIVED_SEMANTIC_INCONSISTENT"
    ]


def test_v2_derived_semantic_change_changes_only_consumption_identity(
    tmp_path: Path,
) -> None:
    artifact = _v2_artifact(tmp_path)
    manifest_path = artifact / "manifests/student_consumption_v2.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest["base_artifact_semantic_digest"]
    original_consumption = manifest["semantic_identity"]["semantic_digest"]
    target = artifact / "resources/00.npz"
    np.savez(
        target,
        input_ids=np.array([[2, 1]], dtype=np.int32),
        attention_mask=np.array([[1, 1]], dtype=np.int32),
        corridor_lengths=np.array([2], dtype=np.int32),
    )
    row = next(item for item in manifest["resources"] if item["role"] == "target_shard")
    row["semantic_digest"] = resource_semantic_digest(
        target, row["encoding"], row["consumption"]
    )
    _refresh_consumption_identity(manifest)
    _rewrite_manifest_inventory(artifact, manifest)
    result = validate_and_resolve_student_consumption(
        artifact, profile_id="native_v3_student_v2"
    )
    assert result.ok, result.issues
    assert result.descriptor is not None
    assert result.descriptor.base_artifact_semantic_digest == base
    assert result.descriptor.consumption_semantic_digest != original_consumption


def test_v2_resource_relocation_changes_raw_inventory_not_consumption_identity(
    tmp_path: Path,
) -> None:
    artifact = _v2_artifact(tmp_path)
    manifest_path = artifact / "manifests/student_consumption_v2.json"
    manifest = json.loads(manifest_path.read_text())
    old_identity = manifest["semantic_identity"]["semantic_digest"]
    base = manifest["base_artifact_semantic_digest"]
    cover_before = _sha256(artifact / "cover_page.json")
    row = next(item for item in manifest["resources"] if item["role"] == "target_shard")
    old = artifact / row["inventory_binding"]
    new_relative = "relocated/target.npz"
    new = artifact / new_relative
    new.parent.mkdir()
    old.rename(new)
    row["inventory_binding"] = new_relative
    cover = json.loads((artifact / "cover_page.json").read_text())
    inventory = cover["manifests"]["content"]["inventory"]
    entry = next(item for item in inventory if item["path"] == "resources/00.npz")
    entry["path"] = new_relative
    (artifact / "cover_page.json").write_text(json.dumps(cover, sort_keys=True))
    _rewrite_manifest_inventory(artifact, manifest)
    result = validate_and_resolve_student_consumption(
        artifact, profile_id="native_v3_student_v2"
    )
    assert result.ok, result.issues
    assert result.descriptor is not None
    assert result.descriptor.consumption_semantic_digest == old_identity
    assert result.descriptor.base_artifact_semantic_digest == base
    assert _sha256(artifact / "cover_page.json") != cover_before
