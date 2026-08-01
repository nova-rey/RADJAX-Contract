"""Material delivery corpus for the native-v3 Student-consumption contract.

The test builder intentionally writes bytes to an isolated temporary corpus;
the checked-in manifest vectors pin the normative shape while this suite proves
the public resolver handles the three supported physical deliveries.
"""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import numpy as np
import pytest
from test_tome_contract_publication import (
    _canonical_tgz,
    _refresh_sidecar_inventory,
    _sha256,
    _student_artifact,
    _write_manifest_then_refresh,
)

from radjax_contract.tome import student_consumption as student_consumption_module
from radjax_contract.tome import validate_and_resolve_student_consumption

FIXTURE_ROOT = (
    Path(__file__).parents[1]
    / "src/radjax_contract/contracts/radjax_tome/student_consumption/v1/fixtures"
)


def _corpus_artifact(root: Path) -> Path:
    return _student_artifact(
        root, source_vector=FIXTURE_ROOT / "valid/native_v3_student_v1.json"
    )


def _archive(root: Path, destination: Path) -> None:
    with tarfile.open(destination, "w") as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            archive.add(path, arcname=path.relative_to(root).as_posix())


def test_material_corpus_validates_directory_rtome_and_canonical_tgz(
    tmp_path: Path,
) -> None:
    directory = _corpus_artifact(tmp_path / "directory")
    directory_result = validate_and_resolve_student_consumption(directory)
    assert directory_result.ok and directory_result.descriptor is not None

    cover_path = directory / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    cover["package"]["transport"] = "rtome"
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    rtome = tmp_path / "student.rtome"
    _archive(directory, rtome)
    rtome_result = validate_and_resolve_student_consumption(rtome)
    assert rtome_result.ok and rtome_result.descriptor is not None

    cover["package"]["transport"] = "tgz"
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    tgz = tmp_path / "student.tgz"
    _canonical_tgz(directory, tgz)
    tgz_result = validate_and_resolve_student_consumption(tgz, strict=True)
    assert tgz_result.ok and tgz_result.descriptor is not None
    assert {
        directory_result.descriptor.consumption_semantic_digest,
        rtome_result.descriptor.consumption_semantic_digest,
        tgz_result.descriptor.consumption_semantic_digest,
    } == {directory_result.descriptor.consumption_semantic_digest}


def test_material_corpus_catalog_declares_its_pinned_source_and_runner() -> None:
    catalog = json.loads((FIXTURE_ROOT / "catalog.json").read_text(encoding="utf-8"))
    source = FIXTURE_ROOT / catalog["source_asset"]
    assert source.is_file()
    assert (
        catalog["materializer"] == "tests/test_student_consumption_material_corpus.py"
    )


def test_material_corpus_materializes_the_complete_normative_vector(
    tmp_path: Path,
) -> None:
    source = FIXTURE_ROOT / "valid/native_v3_student_v1.json"
    expected_manifest = json.loads(source.read_text(encoding="utf-8"))
    expected = json.loads(
        (FIXTURE_ROOT.parent / "vectors/descriptor_serialization_v1.json").read_text(
            encoding="utf-8"
        )
    )["normative_material_descriptor"]
    artifact = _corpus_artifact(tmp_path)
    manifest = json.loads(
        (artifact / "manifests/student_consumption_v1.json").read_text(encoding="utf-8")
    )
    result = validate_and_resolve_student_consumption(artifact)
    assert result.ok and result.descriptor is not None
    assert manifest["resources"] == expected_manifest["resources"]
    assert manifest["semantic_identity"] == expected_manifest["semantic_identity"]
    assert manifest["joins"] == expected_manifest["joins"]
    assert manifest["provenance"] == expected_manifest["provenance"]
    assert result.descriptor.profile_id == expected["profile_id"]
    assert (
        result.descriptor.base_artifact_semantic_digest
        == expected["base_artifact_semantic_digest"]
    )
    assert (
        result.descriptor.consumption_semantic_digest
        == expected["consumption_semantic_digest"]
    )
    assert result.descriptor.vocabulary == expected["vocabulary"]
    assert result.descriptor.sequence == expected["sequence"]
    resolved_ids = [
        resource.resource_id
        for group in (
            result.descriptor.corridor_resources,
            result.descriptor.exemplar_resources,
            result.descriptor.validation_resources,
        )
        for resource in group
    ]
    assert sorted(resolved_ids) == sorted(expected["resource_ids"])


def test_material_corpus_rejects_legacy_json_corridor_assignment(
    tmp_path: Path,
) -> None:
    artifact = _corpus_artifact(tmp_path)
    legacy_locator = "resources/legacy-corridor-assignment.json"
    legacy_path = artifact / legacy_locator
    legacy_path.write_text(
        json.dumps(
            {
                "position_example_index": [0, 0],
                "position": [0, 1],
                "mode_id": [0, 0],
                "weight": [1.0, 1.0],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = artifact / "manifests/student_consumption_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assignment = next(
        resource
        for resource in manifest["resources"]
        if resource["role"] == "corridor_assignment"
    )
    assignment["training_payload_binding"] = legacy_locator
    assignment["inventory_binding"] = legacy_locator
    assignment["encoding"] = "json"
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    training = cover["identity"]["training_payload"]
    training_entry = next(
        item
        for item in training
        if item["semantic_digest"] == assignment["semantic_digest"]
    )
    training_entry["logical_id"] = legacy_locator
    cover["manifests"]["content"]["inventory"].append(
        {
            "path": legacy_locator,
            "sha256": _sha256(legacy_path),
            "size_bytes": legacy_path.stat().st_size,
            "classification": "training_payload",
            "training_authoritative": True,
        }
    )
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    _refresh_sidecar_inventory(artifact)
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == [
        "TSC030_CONTAINER_ENCODING_MISMATCH"
    ]


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("assignment_missing", "TSC041_ASSIGNMENT_MISSING"),
        ("assignment_duplicate", "TSC042_ASSIGNMENT_DUPLICATE"),
        ("mode_unknown", "TSC043_MODE_UNKNOWN"),
        ("negative_weight", "TSC045_WEIGHT_INVALID"),
        ("assignment_coordinate", "TSC040_ASSIGNMENT_COORDINATE"),
    ],
)
def test_material_corpus_executes_corridor_mutations(
    tmp_path: Path, mutation: str, code: str
) -> None:
    artifact = _corpus_artifact(tmp_path)
    path = artifact / "resources/03.npz"
    arrays = {
        "position_example_index": np.array([0, 0], dtype=np.int32),
        "position": np.array([0, 1], dtype=np.int32),
        "mode_id": np.array([0, 0], dtype=np.int32),
        "weight": np.array([1.0, 1.0], dtype=np.float32),
    }
    if mutation == "assignment_missing":
        arrays = {key: value[:1] for key, value in arrays.items()}
        count = 1
    elif mutation == "assignment_duplicate":
        arrays = {
            "position_example_index": np.array([0, 0, 0], dtype=np.int32),
            "position": np.array([0, 0, 1], dtype=np.int32),
            "mode_id": np.array([0, 0, 0], dtype=np.int32),
            "weight": np.array([1.0, 1.0, 1.0], dtype=np.float32),
        }
        count = 3
    elif mutation == "mode_unknown":
        arrays["mode_id"] = np.array([99, 0], dtype=np.int32)
        count = 2
    elif mutation == "assignment_coordinate":
        arrays = {
            "position_example_index": np.array([0, 0, 0], dtype=np.int32),
            "position": np.array([0, 1, 2], dtype=np.int32),
            "mode_id": np.array([0, 0, 0], dtype=np.int32),
            "weight": np.array([1.0, 1.0, 1.0], dtype=np.float32),
        }
        count = 3
    else:
        arrays["weight"] = np.array([-1.0, 1.0], dtype=np.float32)
        count = 2
    np.savez(path, **arrays)
    if count != 2:
        np.savez(
            artifact / "resources/06.npz",
            **{
                name: np.full(count, 0.5, dtype=np.float32)
                for name in (
                    "entropy",
                    "top1_margin",
                    "top8_mass",
                    "top32_mass",
                    "tail_mass",
                )
            },
        )
    _refresh_sidecar_inventory(artifact)
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == [code]


def test_material_corpus_executes_mode_bounds_mutation(tmp_path: Path) -> None:
    artifact = _corpus_artifact(tmp_path)
    path = artifact / "resources/02.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["modes"][0]["bounds"]["entropy"] = {"min": 1.0, "max": 0.0}
    path.write_text(json.dumps(payload), encoding="utf-8")
    _refresh_sidecar_inventory(artifact)
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == ["TSC044_MODE_BOUNDS_INVALID"]


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("passport_mismatch", "TSC050_PASSPORT_JOIN_INVALID"),
        ("rank_gap", "TSC051_EXEMPLAR_RANK_INVALID"),
        ("top_k_mask", "TSC052_DYNAMIC_TOPK_INVALID"),
        ("mass_sum", "TSC053_PROBABILITY_MASS_INVALID"),
        ("corridor_link", "TSC054_CORRIDOR_LINKAGE_INVALID"),
        ("delivery_path", "TSC055_PROVENANCE_CONTRADICTION"),
    ],
)
def test_material_corpus_executes_exemplar_mutations(
    tmp_path: Path, mutation: str, code: str
) -> None:
    artifact = _corpus_artifact(tmp_path)
    exemplar_path = artifact / "resources/05.json"
    exemplar = json.loads(exemplar_path.read_text(encoding="utf-8"))
    row = exemplar["selected_exemplars"][0]
    if mutation == "passport_mismatch":
        row["selected_example_id"] = "other-example"
    elif mutation == "rank_gap":
        row["rank"] = 2
    elif mutation == "top_k_mask":
        row["top_selection_mask"] = [True, False, True]
    elif mutation == "mass_sum":
        row["top_mass"] = 0.5
    elif mutation == "corridor_link":
        row["corridor_mode_id"] = 99
    else:
        row["source_delivery_path"] = "not-a-path"
    exemplar_path.write_text(json.dumps(exemplar), encoding="utf-8")
    _refresh_sidecar_inventory(artifact)
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == [code]


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("legacy", "TSC001_PROFILE_UNSUPPORTED"),
        ("cover", "TSC002_COVER_VERSION_UNSUPPORTED"),
        ("capability", "TSC003_REQUIRED_CAPABILITY_UNKNOWN"),
        ("digest_method", "TSC004_DIGEST_METHOD_UNSUPPORTED"),
        ("transport", "TSC020_TRANSPORT_UNSUPPORTED"),
        ("stale_identity", "TSC061_CONSUMPTION_DIGEST_MISMATCH"),
        ("base_identity", "TSC062_BASE_IDENTITY_MISMATCH"),
    ],
)
def test_material_corpus_executes_admission_and_identity_mutations(
    tmp_path: Path, mutation: str, code: str
) -> None:
    artifact = _corpus_artifact(tmp_path)
    cover_path = artifact / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    if mutation == "legacy":
        cover["schema_version"] = "radjax_tome_cover_v3"
    elif mutation == "cover":
        cover["schema_version"] = "unsupported"
    elif mutation == "capability":
        cover["student_consumption"]["required_capabilities"] = ["unknown"]
    elif mutation == "digest_method":
        cover["student_consumption"]["digest_method"] = "sha512"
    elif mutation == "transport":
        cover["package"]["transport"] = "tgz"
    elif mutation == "stale_identity":
        manifest_path = artifact / "manifests/student_consumption_v1.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["semantic_identity"]["vocabulary"]["vocab_size"] = 9
        _write_manifest_then_refresh(artifact, manifest)
        result = validate_and_resolve_student_consumption(artifact)
        assert [issue.code for issue in result.issues] == [code]
        return
    else:
        cover["identity"]["semantic_digest"] = "sha256:" + "d" * 64
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    result = validate_and_resolve_student_consumption(artifact)
    assert [issue.code for issue in result.issues] == [code]


@pytest.mark.parametrize("limit", ["member", "total", "ratio", "fifo"])
def test_material_corpus_executes_archive_safety_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    archive_path = tmp_path / f"{limit}.tgz"
    with tarfile.open(archive_path, "w:gz") as archive:
        if limit == "fifo":
            member = tarfile.TarInfo("pipe")
            member.type = tarfile.FIFOTYPE
            archive.addfile(member)
        else:
            for name in ("a", "b"):
                payload = b"x" * 64
                member = tarfile.TarInfo(name)
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
    if limit == "member":
        monkeypatch.setattr(student_consumption_module, "_MAX_MEMBER_BYTES", 1)
    elif limit == "total":
        monkeypatch.setattr(student_consumption_module, "_MAX_TOTAL_BYTES", 1)
    elif limit == "ratio":
        monkeypatch.setattr(student_consumption_module, "_MAX_COMPRESSION_RATIO", 1)
    result = validate_and_resolve_student_consumption(archive_path)
    assert [issue.code for issue in result.issues] == ["TSC021_TRANSPORT_UNSAFE"]
