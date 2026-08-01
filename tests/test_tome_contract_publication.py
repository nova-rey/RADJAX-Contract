from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import numpy as np
import pytest

from radjax_contract.tome import (
    TOME_CONTRACT_ID,
    TOME_CONTRACT_PUBLICATION_VERSION,
    TOME_STREAMING_CONTRACT_PUBLICATION_VERSION,
    TOME_STUDENT_CONSUMPTION_CONTRACT_ID,
    TOME_STUDENT_CONSUMPTION_CONTRACT_PUBLICATION_VERSION,
    open_streaming_tome,
    open_verified_student_resource,
    tome_contract_asset_path,
    tome_contract_root,
    tome_streaming_contract_asset_path,
    tome_streaming_contract_root,
    tome_student_consumption_contract_asset_path,
    tome_student_consumption_contract_root,
    validate_and_resolve_student_consumption,
    validate_streaming_tome,
)


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _student_artifact(root: Path) -> Path:
    roles = [
        "target_shard",
        "example_registry",
        "corridor_mode_table",
        "corridor_assignment",
        "selected_passport_index",
        "selected_exemplar_payload",
        "corridor_observed_statistics",
        "row_range_declaration",
        "delivery_receipt",
        "authority_reference",
    ]
    resources = []
    training = []
    inventory = []
    for index, role in enumerate(roles):
        relative = f"resources/{index:02d}.json"
        encoding = "json"
        if role in {
            "target_shard",
            "corridor_assignment",
            "corridor_observed_statistics",
        }:
            relative = f"resources/{index:02d}.npz"
            encoding = "npz"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if role == "target_shard":
            np.savez(
                path,
                input_ids=np.array([[1, 2]], dtype=np.int32),
                attention_mask=np.array([[1, 1]], dtype=np.int32),
                corridor_lengths=np.array([2], dtype=np.int32),
            )
        elif role == "corridor_assignment":
            np.savez(
                path,
                position_example_index=np.array([0, 0], dtype=np.int32),
                position=np.array([0, 1], dtype=np.int32),
                mode_id=np.array([0, 0], dtype=np.int32),
                weight=np.array([1.0, 1.0], dtype=np.float32),
            )
        elif role == "corridor_observed_statistics":
            np.savez(
                path,
                entropy=np.array([0.5, 0.5], dtype=np.float32),
                top1_margin=np.array([0.5, 0.5], dtype=np.float32),
                top8_mass=np.array([0.5, 0.5], dtype=np.float32),
                top32_mass=np.array([0.5, 0.5], dtype=np.float32),
                tail_mass=np.array([0.5, 0.5], dtype=np.float32),
            )
        elif role == "corridor_mode_table":
            bounds = {
                name: {"min": 0.0, "max": 1.0}
                for name in (
                    "entropy",
                    "top1_margin",
                    "top8_mass",
                    "top32_mass",
                    "tail_mass",
                )
            }
            path.write_text(
                json.dumps({"modes": [{"mode_id": 0, "bounds": bounds}]}),
                encoding="utf-8",
            )
        elif role in {"selected_passport_index", "selected_exemplar_payload"}:
            path.write_text(json.dumps({"selected_exemplars": []}), encoding="utf-8")
        else:
            path.write_text("{}", encoding="utf-8")
        semantic = f"sha256:{index + 1:064x}"
        resources.append(
            {
                "resource_id": f"{role}/default",
                "role": role,
                "instance_id": "default",
                "semantic_digest": semantic,
                "training_payload_binding": relative,
                "inventory_binding": relative,
                "encoding": encoding,
                "classification": "validation",
                "consumption": (
                    {"row_start": 0, "row_end": 1}
                    if role == "target_shard"
                    else {"kind": role}
                ),
            }
        )
        training.append({"logical_id": relative, "semantic_digest": semantic})
        inventory.append(
            {
                "path": relative,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    identity = {
        "schema_version": "radjax_tome_student_consumption_semantic_identity_v1",
        "profile_id": "native_v3_student_v1",
        "vocabulary": {"vocab_size": 8},
        "sequence": {"sequence_length": 2, "alignment": "teacher_logit_position"},
        "resources": [
            {
                key: item[key]
                for key in ("resource_id", "role", "instance_id", "semantic_digest")
            }
            for item in resources
        ],
        "joins": [],
        "authority": {},
    }
    identity["semantic_digest"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    manifest = {
        "schema_version": "radjax_tome_student_consumption_manifest_v1",
        "profile_id": "native_v3_student_v1",
        "base_artifact_semantic_digest": "sha256:" + "a" * 64,
        "semantic_identity": identity,
        "resources": resources,
        "joins": [],
        "provenance": {"delivery_path": "two_pass_rerun_selected"},
    }
    manifest_path = root / "manifests/student_consumption_v1.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    inventory.append(
        {
            "path": "manifests/student_consumption_v1.json",
            "sha256": _sha256(manifest_path),
            "size_bytes": manifest_path.stat().st_size,
        }
    )
    cover = {
        "schema_version": "radjax_tome_cover_v3_student_consumption_v1",
        "identity": {
            "semantic_digest": "sha256:" + "a" * 64,
            "training_payload": training,
        },
        "package": {"transport": "directory"},
        "manifests": {
            "content": {
                "semantic_identity_digest": "sha256:" + "a" * 64,
                "inventory": inventory,
            }
        },
        "student_consumption": {
            "manifest_path": "manifests/student_consumption_v1.json",
            "manifest_sha256": _sha256(manifest_path),
            "semantic_digest": identity["semantic_digest"],
        },
    }
    (root / "cover_page.json").write_text(json.dumps(cover), encoding="utf-8")
    return root


def _refresh_sidecar_inventory(root: Path) -> None:
    cover_path = root / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    manifest_path = root / cover["student_consumption"]["manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inventory = cover["manifests"]["content"]["inventory"]
    for resource in manifest["resources"]:
        path = root / resource["inventory_binding"]
        entry = next(
            item for item in inventory if item["path"] == resource["inventory_binding"]
        )
        entry["sha256"] = _sha256(path)
        entry["size_bytes"] = path.stat().st_size
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    manifest_entry = next(
        item
        for item in inventory
        if item["path"] == "manifests/student_consumption_v1.json"
    )
    manifest_entry["sha256"] = _sha256(manifest_path)
    manifest_entry["size_bytes"] = manifest_path.stat().st_size
    cover["student_consumption"]["manifest_sha256"] = manifest_entry["sha256"]
    cover_path.write_text(json.dumps(cover), encoding="utf-8")


def test_v3_contract_resources_are_packaged_and_checksum_pinned() -> None:
    root = tome_contract_root()
    assert TOME_CONTRACT_ID == "radjax_tome_artifact_contract"
    assert TOME_CONTRACT_PUBLICATION_VERSION == "1.0.0"
    contract = json.loads((root / "contract.json").read_text(encoding="utf-8"))
    assert contract["publication_version"] == "1.0.0"
    expected = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", maxsplit=1)
        expected[relative] = digest
    observed = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert expected == observed


def test_v3_contract_resource_lookup_rejects_unsafe_or_unknown_paths() -> None:
    assert tome_contract_asset_path("contract.json").is_file()
    with pytest.raises(ValueError, match="normalized relative"):
        tome_contract_asset_path("../contract.json")
    with pytest.raises(ValueError, match="unknown"):
        tome_contract_asset_path("missing.json")


def test_m7_streaming_contract_resources_are_packaged_and_checksum_pinned() -> None:
    root = tome_streaming_contract_root()
    assert TOME_CONTRACT_ID == "radjax_tome_artifact_contract"
    assert TOME_STREAMING_CONTRACT_PUBLICATION_VERSION == "2.0.0"
    contract = json.loads((root / "contract.json").read_text(encoding="utf-8"))
    assert contract["publication_version"] == "2.0.0"
    expected = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", maxsplit=1)
        expected[relative] = digest
    observed = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert expected == observed


def test_m7_streaming_resource_lookup_rejects_unsafe_or_unknown_paths() -> None:
    assert tome_streaming_contract_asset_path(
        "schemas/payload_layout_v1.json"
    ).is_file()
    with pytest.raises(ValueError, match="normalized relative"):
        tome_streaming_contract_asset_path("../contract.json")
    with pytest.raises(ValueError, match="unknown"):
        tome_streaming_contract_asset_path("missing.json")


def test_student_consumption_contract_resources_are_discoverable_and_pinned() -> None:
    root = tome_student_consumption_contract_root()
    assert (
        TOME_STUDENT_CONSUMPTION_CONTRACT_ID
        == "radjax_tome_student_consumption_contract"
    )
    assert TOME_STUDENT_CONSUMPTION_CONTRACT_PUBLICATION_VERSION == "1.0.0-draft"
    contract = json.loads((root / "contract.json").read_text(encoding="utf-8"))
    assert contract["contract_id"] == TOME_STUDENT_CONSUMPTION_CONTRACT_ID
    assert contract["publication_version"] == (
        TOME_STUDENT_CONSUMPTION_CONTRACT_PUBLICATION_VERSION
    )
    assert tome_student_consumption_contract_asset_path(
        "profiles/native_v3_student_v1.json"
    ).is_file()
    with pytest.raises(ValueError, match="normalized relative"):
        tome_student_consumption_contract_asset_path("../contract.json")
    with pytest.raises(ValueError, match="unknown"):
        tome_student_consumption_contract_asset_path("missing.json")


def test_legacy_v3_is_not_silently_reinterpreted_as_student_consumable(
    tmp_path: Path,
) -> None:
    (tmp_path / "cover_page.json").write_text(
        json.dumps({"schema_version": "radjax_tome_cover_v3"}), encoding="utf-8"
    )
    result = validate_and_resolve_student_consumption(tmp_path)
    assert result.ok is False
    assert result.descriptor is None
    assert [issue.code for issue in result.issues] == ["TSC001_PROFILE_UNSUPPORTED"]


def test_student_consumption_resolver_validates_real_sidecar_bindings(
    tmp_path: Path,
) -> None:
    result = validate_and_resolve_student_consumption(_student_artifact(tmp_path))
    assert result.ok
    assert result.descriptor is not None
    assert result.descriptor.sequence["alignment"] == "teacher_logit_position"
    assert len(result.descriptor.validation_resources) == 4


def test_student_consumption_resolver_rejects_semantically_invalid_token_domain(
    tmp_path: Path,
) -> None:
    artifact = _student_artifact(tmp_path)
    target_path = artifact / "resources/00.npz"
    np.savez(
        target_path,
        input_ids=np.array([[1, 8]], dtype=np.int32),
        attention_mask=np.array([[1, 1]], dtype=np.int32),
        corridor_lengths=np.array([2], dtype=np.int32),
    )
    _refresh_sidecar_inventory(artifact)
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == ["TSC034_TOKEN_DOMAIN"]


def test_student_consumption_resolver_accepts_transport_neutral_tgz(
    tmp_path: Path,
) -> None:
    artifact = _student_artifact(tmp_path / "directory")
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    cover["package"]["transport"] = "tgz"
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    archive_path = tmp_path / "student.tgz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(item for item in artifact.rglob("*") if item.is_file()):
            archive.add(path, arcname=path.relative_to(artifact).as_posix())
    directory_result = validate_and_resolve_student_consumption(artifact)
    archive_result = validate_and_resolve_student_consumption(archive_path)
    assert directory_result.ok is False  # declaration/container mismatch is explicit
    assert archive_result.ok
    assert archive_result.descriptor is not None
    assert archive_result.descriptor.delivery["transport"] == "tgz"


def test_verified_student_resource_uses_stable_resource_id(tmp_path: Path) -> None:
    artifact = _student_artifact(tmp_path)
    with open_verified_student_resource(artifact, "target_shard/default") as handle:
        assert handle.read(2) == b"PK"
    with pytest.raises(ValueError, match="unknown Student-consumption resource"):
        with open_verified_student_resource(artifact, "resources/00.json"):
            pass


def test_student_consumption_resolver_rejects_transport_declaration_mismatch(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "mismatch.tgz"
    cover = {
        "schema_version": "radjax_tome_cover_v3_student_consumption_v1",
        "package": {"transport": "directory"},
    }
    with tarfile.open(archive_path, "w:gz") as archive:
        payload = json.dumps(cover).encode("utf-8")
        member = tarfile.TarInfo("cover_page.json")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    result = validate_and_resolve_student_consumption(archive_path)
    assert [issue.code for issue in result.issues] == ["TSC020_TRANSPORT_UNSUPPORTED"]


@pytest.mark.parametrize("cover", ["[]", '{"schema_version":"x","schema_version":"x"}'])
def test_student_consumption_resolver_fails_closed_for_non_object_or_duplicate_json(
    tmp_path: Path, cover: str
) -> None:
    (tmp_path / "cover_page.json").write_text(cover, encoding="utf-8")
    result = validate_and_resolve_student_consumption(tmp_path)
    assert result.ok is False
    assert [issue.code for issue in result.issues] == [
        "TSC060_CONSUMPTION_CANONICALIZATION"
    ]


def test_m7_streaming_validator_is_a_portable_contract_primitive(
    tmp_path: Path,
) -> None:
    report = validate_streaming_tome(tmp_path)
    assert report.ok is False
    assert report.errors == ("shape_invalid",)


def test_m7_archive_transport_declaration_mismatch_fails_explicitly(
    tmp_path: Path,
) -> None:
    """A .tgz cannot silently claim to be a directory package."""

    archive_path = tmp_path / "mismatch.tgz"
    cover = {
        "schema_version": "radjax_tome_cover_v4",
        "identity": {},
        "training": {},
        "package": {"profile": "student", "transport": "directory"},
        "manifests": {},
        "authority": {},
        "provenance": {},
        "validation": {},
    }
    with tarfile.open(archive_path, "w:gz") as archive:
        content = json.dumps(cover).encode("utf-8")
        member = tarfile.TarInfo("cover_page.json")
        member.size = len(content)
        member.mtime = 0
        member.uid = member.gid = 0
        member.uname = member.gname = ""
        member.mode = 0o644
        archive.addfile(member, io.BytesIO(content))

    report = validate_streaming_tome(archive_path)
    assert report.ok is False
    assert report.errors == ("transport_mismatch",)
    with pytest.raises(ValueError, match="transport_mismatch"):
        open_streaming_tome(archive_path)
