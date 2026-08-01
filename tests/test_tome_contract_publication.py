from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator

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
        elif role == "example_registry":
            path.write_text(
                json.dumps(
                    {
                        "examples": [
                            {
                                "global_example_index": 0,
                                "selected_example_id": "example-0",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
        elif role in {"selected_passport_index", "selected_exemplar_payload"}:
            record = {
                "rank": 1,
                "selected_example_id": "example-0",
                "selected_position": 0,
                "source_shard_id": 0,
                "source_row": 0,
                "source_position": 0,
                "source_delivery_path": "two_pass_rerun_selected",
                "corridor_mode_id": 0,
            }
            if role == "selected_exemplar_payload":
                record.update(
                    {
                        "top_token_ids": [1, 2, 0],
                        "top_probs": [0.6, 0.3, 0.0],
                        "top_log_probs": [
                            -0.5108256238,
                            -1.2039728043,
                            -100.0,
                        ],
                        "top_selection_mask": [True, True, False],
                        "effective_top_k": 2,
                        "top_mass": 0.9,
                        "tail_mass": 0.1,
                        "bucket_masses": [0.04, 0.06],
                    }
                )
            path.write_text(
                json.dumps({"selected_exemplars": [record]}), encoding="utf-8"
            )
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
                "classification": (
                    "batch"
                    if role
                    in {
                        "target_shard",
                        "example_registry",
                        "corridor_mode_table",
                        "corridor_assignment",
                        "selected_passport_index",
                        "selected_exemplar_payload",
                    }
                    else "provenance"
                    if role == "delivery_receipt"
                    else "validation"
                ),
                "consumption": (
                    {"row_start": 0, "row_end": 1}
                    if role == "target_shard"
                    else {"ordering": "global_example_index"}
                    if role == "example_registry"
                    else {"ordering": "global_example_index_position"}
                    if role == "corridor_assignment"
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
                "classification": "training_payload",
                "training_authoritative": True,
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
        "joins": [
            {"kind": "assignment_to_logit_position"},
            {"kind": "exemplar_to_passport"},
            {"kind": "exemplar_to_corridor"},
        ],
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
        "joins": [
            {"kind": "assignment_to_logit_position"},
            {"kind": "exemplar_to_passport"},
            {"kind": "exemplar_to_corridor"},
        ],
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
            "classification": "manifest",
            "training_authoritative": False,
        }
    )
    cover = {
        "schema_version": "radjax_tome_cover_v3_student_consumption_v1",
        "identity": {
            "semantic_digest": "sha256:" + "a" * 64,
            "training_payload": training,
        },
        "training": {},
        "package": {"transport": "directory"},
        "manifests": {
            "content": {
                "schema_version": "tome_content_manifest_v2",
                "profile": "student",
                "semantic_identity_digest": "sha256:" + "a" * 64,
                "inventory": inventory,
                "manifest_digest": "sha256:" + "b" * 64,
            }
        },
        "authority": {},
        "provenance": {},
        "validation": {},
        "student_consumption": {
            "profile_id": "native_v3_student_v1",
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


def _refresh_semantic_projection(root: Path) -> None:
    """Refresh a deliberate semantic mutation without changing its raw binding."""

    manifest_path = root / "manifests/student_consumption_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    identity = manifest["semantic_identity"]
    identity["resources"] = [
        {
            key: row[key]
            for key in ("resource_id", "role", "instance_id", "semantic_digest")
        }
        for row in manifest["resources"]
    ]
    identity.pop("semantic_digest", None)
    identity["semantic_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    cover_path = root / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    cover["student_consumption"]["semantic_digest"] = identity["semantic_digest"]
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    _refresh_sidecar_inventory(root)


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
    contract_root = tome_student_consumption_contract_root()
    descriptor_schema = json.loads(
        (contract_root / "schemas/student_consumption_descriptor_v1.json").read_text(
            encoding="utf-8"
        )
    )
    result_schema = json.loads(
        (
            contract_root / "schemas/student_consumption_validation_result_v1.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator(descriptor_schema).validate(result.descriptor.to_dict())
    Draft202012Validator(result_schema).validate(result.to_dict())


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


@pytest.mark.parametrize(
    ("arrays", "code"),
    [
        (
            {
                "input_ids": np.array([[1, 2]], dtype=np.float32),
                "attention_mask": np.array([[1, 1]], dtype=np.int32),
                "corridor_lengths": np.array([2], dtype=np.int32),
            },
            "TSC031_DTYPE_MISMATCH",
        ),
        (
            {
                "input_ids": np.array([1, 2], dtype=np.int32),
                "attention_mask": np.array([1, 1], dtype=np.int32),
                "corridor_lengths": np.array([2], dtype=np.int32),
            },
            "TSC032_RANK_SHAPE_AXIS_MISMATCH",
        ),
        (
            {
                "input_ids": np.array([[1, 2]], dtype=np.int32),
                "attention_mask": np.array([[1, 0]], dtype=np.int32),
                "corridor_lengths": np.array([2], dtype=np.int32),
            },
            "TSC035_MASK_LENGTH_ALIGNMENT",
        ),
    ],
)
def test_student_consumption_rejects_target_array_contract_mutations(
    tmp_path: Path, arrays: dict[str, np.ndarray], code: str
) -> None:
    artifact = _student_artifact(tmp_path)
    np.savez(artifact / "resources/00.npz", **arrays)
    _refresh_sidecar_inventory(artifact)
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == [code]


def test_student_consumption_rejects_noncontiguous_target_shard_ranges(
    tmp_path: Path,
) -> None:
    artifact = _student_artifact(tmp_path)
    manifest_path = artifact / "manifests/student_consumption_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = next(row for row in manifest["resources"] if row["role"] == "target_shard")
    target["consumption"] = {"row_start": 1, "row_end": 2}
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _refresh_sidecar_inventory(artifact)
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == ["TSC033_SHARD_CARDINALITY_ORDER"]


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


def test_student_consumption_reports_safe_noncanonical_archive_and_strict_rejects(
    tmp_path: Path,
) -> None:
    artifact = _student_artifact(tmp_path / "directory")
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    cover["package"]["transport"] = "tgz"
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    archive_path = tmp_path / "noncanonical.tgz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(item for item in artifact.rglob("*") if item.is_file()):
            archive.add(path, arcname=path.relative_to(artifact).as_posix())
    permissive = validate_and_resolve_student_consumption(archive_path)
    strict = validate_and_resolve_student_consumption(archive_path, strict=True)
    assert permissive.ok
    assert [warning.code for warning in permissive.warnings] == [
        "TSC020_TRANSPORT_NONCANONICAL"
    ] * len(permissive.warnings)
    assert permissive.warnings
    assert strict.ok is False
    assert [issue.code for issue in strict.issues] == [
        "TSC020_TRANSPORT_NONCANONICAL"
    ] * len(strict.issues)


def test_student_consumption_resolver_accepts_transport_neutral_rtome(
    tmp_path: Path,
) -> None:
    artifact = _student_artifact(tmp_path / "directory")
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    cover["package"]["transport"] = "rtome"
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    archive_path = tmp_path / "student.rtome"
    with tarfile.open(archive_path, "w") as archive:
        for path in sorted(item for item in artifact.rglob("*") if item.is_file()):
            archive.add(path, arcname=path.relative_to(artifact).as_posix())
    result = validate_and_resolve_student_consumption(archive_path)
    assert result.ok
    assert result.descriptor is not None
    assert result.descriptor.delivery["transport"] == "rtome"


def test_student_consumption_identity_survives_physical_relocation(
    tmp_path: Path,
) -> None:
    artifact = _student_artifact(tmp_path)
    before = validate_and_resolve_student_consumption(artifact)
    assert before.ok and before.descriptor is not None
    old = artifact / "resources/00.npz"
    new = artifact / "relocated/target.npz"
    new.parent.mkdir()
    old.replace(new)
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    manifest_path = artifact / "manifests/student_consumption_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = next(
        item for item in manifest["resources"] if item["role"] == "target_shard"
    )
    target["training_payload_binding"] = "relocated/target.npz"
    target["inventory_binding"] = "relocated/target.npz"
    training = cover["identity"]["training_payload"]
    training[0]["logical_id"] = "relocated/target.npz"
    inventory = cover["manifests"]["content"]["inventory"]
    entry = next(item for item in inventory if item["path"] == "resources/00.npz")
    entry["path"] = "relocated/target.npz"
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
    after = validate_and_resolve_student_consumption(artifact)
    assert after.ok and after.descriptor is not None
    assert (
        after.descriptor.consumption_semantic_digest
        == before.descriptor.consumption_semantic_digest
    )


def test_student_consumption_identity_ignores_delivery_path_provenance(
    tmp_path: Path,
) -> None:
    artifact = _student_artifact(tmp_path)
    before = validate_and_resolve_student_consumption(artifact)
    assert before.ok and before.descriptor is not None
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    manifest_path = artifact / "manifests/student_consumption_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["provenance"]["delivery_path"] = "one_pass_pruned_candidate"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    inventory = cover["manifests"]["content"]["inventory"]
    manifest_entry = next(
        item
        for item in inventory
        if item["path"] == "manifests/student_consumption_v1.json"
    )
    manifest_entry["sha256"] = _sha256(manifest_path)
    manifest_entry["size_bytes"] = manifest_path.stat().st_size
    cover["student_consumption"]["manifest_sha256"] = manifest_entry["sha256"]
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    after = validate_and_resolve_student_consumption(artifact)
    assert after.ok and after.descriptor is not None
    assert (
        after.descriptor.consumption_semantic_digest
        == before.descriptor.consumption_semantic_digest
    )


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("digest_method", "sha512", "TSC004_DIGEST_METHOD_UNSUPPORTED"),
        ("required_capabilities", ["unknown"], "TSC003_REQUIRED_CAPABILITY_UNKNOWN"),
    ],
)
def test_student_consumption_rejects_unknown_required_negotiation(
    tmp_path: Path, field: str, value: object, code: str
) -> None:
    artifact = _student_artifact(tmp_path)
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    cover["student_consumption"][field] = value
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == [code]


def test_student_consumption_rejects_incomplete_join_declaration(
    tmp_path: Path,
) -> None:
    artifact = _student_artifact(tmp_path)
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    manifest_path = artifact / "manifests/student_consumption_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["joins"] = [{"kind": "assignment_to_logit_position"}]
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    inventory = cover["manifests"]["content"]["inventory"]
    entry = next(
        item
        for item in inventory
        if item["path"] == "manifests/student_consumption_v1.json"
    )
    entry["sha256"] = _sha256(manifest_path)
    entry["size_bytes"] = manifest_path.stat().st_size
    cover["student_consumption"]["manifest_sha256"] = entry["sha256"]
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == ["TSC013_BINDING_ABSENT"]


def test_student_consumption_rejects_duplicate_role_instance_binding(
    tmp_path: Path,
) -> None:
    artifact = _student_artifact(tmp_path)
    manifest_path = artifact / "manifests/student_consumption_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    duplicate = dict(manifest["resources"][0])
    duplicate["resource_id"] = "target_shard/duplicate"
    manifest["resources"].append(duplicate)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _refresh_semantic_projection(artifact)
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == ["TSC011_ROLE_DUPLICATE"]


def test_student_consumption_rejects_unsorted_role_instance_binding(
    tmp_path: Path,
) -> None:
    artifact = _student_artifact(tmp_path)
    manifest_path = artifact / "manifests/student_consumption_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resources"][0], manifest["resources"][1] = (
        manifest["resources"][1],
        manifest["resources"][0],
    )
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _refresh_semantic_projection(artifact)
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == ["TSC012_ROLE_INSTANCE_ORDER"]


def test_student_consumption_rejects_closed_cover_shape_violation(tmp_path: Path) -> None:
    artifact = _student_artifact(tmp_path)
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    del cover["training"]
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == ["TSC002_COVER_VERSION_UNSUPPORTED"]


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
    artifact = _student_artifact(tmp_path / "directory")
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    cover["package"]["transport"] = "directory"
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    archive_path = tmp_path / "mismatch.tgz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(item for item in artifact.rglob("*") if item.is_file()):
            archive.add(path, arcname=path.relative_to(artifact).as_posix())
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
