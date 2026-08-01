"""Material delivery corpus for the native-v3 Student-consumption contract.

The test builder intentionally writes bytes to an isolated temporary corpus;
the checked-in manifest vectors pin the normative shape while this suite proves
the public resolver handles the three supported physical deliveries.
"""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import numpy as np
import pytest
from test_tome_contract_publication import (
    _canonical_tgz,
    _refresh_sidecar_inventory,
    _student_artifact,
)

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
