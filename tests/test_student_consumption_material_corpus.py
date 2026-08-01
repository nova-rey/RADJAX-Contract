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
    _student_artifact,
    _write_manifest_then_refresh,
)

from radjax_contract.tome import student_consumption as student_consumption_module
from radjax_contract.tome import validate_and_resolve_student_consumption


def _archive(root: Path, destination: Path) -> None:
    with tarfile.open(destination, "w") as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            archive.add(path, arcname=path.relative_to(root).as_posix())


def test_material_corpus_validates_directory_rtome_and_canonical_tgz(
    tmp_path: Path,
) -> None:
    directory = _student_artifact(tmp_path / "directory")
    assert validate_and_resolve_student_consumption(directory).ok

    cover_path = directory / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    cover["package"]["transport"] = "rtome"
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    rtome = tmp_path / "student.rtome"
    _archive(directory, rtome)
    assert validate_and_resolve_student_consumption(rtome).ok

    cover["package"]["transport"] = "tgz"
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    tgz = tmp_path / "student.tgz"
    _canonical_tgz(directory, tgz)
    assert validate_and_resolve_student_consumption(tgz, strict=True).ok


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
    artifact = _student_artifact(tmp_path)
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
    artifact = _student_artifact(tmp_path)
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
    artifact = _student_artifact(tmp_path)
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
    artifact = _student_artifact(tmp_path)
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
