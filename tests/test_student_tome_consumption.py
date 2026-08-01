from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from jsonschema import Draft202012Validator

from radjax_contract.tome import (
    CONSUMPTION_CONTRACT_VERSION,
    PROFILE_ID,
    student_consumption_contract_root,
    validate_student_tome_consumption,
)

FIXTURE = (
    Path(__file__).parents[1]
    / "src/radjax_contract/testing/fixtures/native_v3_student_v1/artifact"
)


def test_tome_generated_student_fixture_conforms() -> None:
    result = validate_student_tome_consumption(FIXTURE)
    assert result.ok
    assert result.semantic_digest == (
        "sha256:c7eb093e3481504197018209e94eca41a5b31efc16588d54cc6b453ac1e91d72"
    )


def test_public_profile_assets_are_versioned() -> None:
    root = student_consumption_contract_root()
    contract = _read(root / "contract.json")
    assert PROFILE_ID == "native_v3_student_v1"
    assert CONSUMPTION_CONTRACT_VERSION == "1.0.0"
    assert contract["public_validation_entry_point"] == (
        "radjax_contract.tome.validate_student_tome_consumption"
    )
    assert (root / "schemas/student_consumption_profile_v1.json").is_file()
    assert (root / "fixtures/adversarial/cases.json").is_file()
    schema = _read(root / "schemas/student_consumption_profile_v1.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        _read(root / "profiles/native_v3_student_v1.json")
    )
    expected = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", maxsplit=1)
        expected[relative] = digest
    observed = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert observed == expected


def test_missing_logical_role_has_stable_code(tmp_path: Path) -> None:
    artifact = _copy(tmp_path)
    cover = _read(artifact / "cover_page.json")
    cover["identity"]["training_payload"] = [
        item
        for item in cover["identity"]["training_payload"]
        if item["logical_id"] != "corridors/mode_assignments/weight.npy"
    ]
    _write(artifact / "cover_page.json", cover)
    assert (
        "SC005_LOGICAL_ID_MISSING" in validate_student_tome_consumption(artifact).errors
    )


def test_assignment_weight_and_shape_reject_deterministically(tmp_path: Path) -> None:
    artifact = _copy(tmp_path)
    path = artifact / "corridors/mode_assignments/weight.npy"
    np.save(path, np.array([-1.0], dtype=np.float32), allow_pickle=False)
    _rehash(artifact, "corridors/mode_assignments/weight.npy")
    result = validate_student_tome_consumption(artifact)
    assert "SC012_SHAPE_INVALID" in result.errors
    assert "SC016_WEIGHT_INVALID" in result.errors


def test_exemplar_passport_rejects_deterministically(tmp_path: Path) -> None:
    artifact = _copy(tmp_path)
    relative = "selected_exemplars/selected-exemplars-00000.json"
    payload = _read(artifact / relative)
    payload["selected_exemplars"][0]["selected_position"] = 3
    _write(artifact / relative, payload)
    _rehash(artifact, relative)
    assert (
        "SC019_EXEMPLAR_PASSPORT_INVALID"
        in validate_student_tome_consumption(artifact).errors
    )


def test_delivery_path_is_provenance_but_must_be_known(tmp_path: Path) -> None:
    artifact = _copy(tmp_path)
    relative = "selected_exemplars/selected-exemplars-00000.json"
    payload = _read(artifact / relative)
    payload["selected_exemplars"][0]["source_delivery_path"] = "secret_path_c"
    _write(artifact / relative, payload)
    _rehash(artifact, relative)
    result = validate_student_tome_consumption(artifact)
    assert "SC021_DELIVERY_PROVENANCE_INVALID" in result.errors


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "artifact"
    shutil.copytree(FIXTURE, target)
    return target


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _rehash(artifact: Path, relative: str) -> None:
    cover = _read(artifact / "cover_page.json")
    path = artifact / relative
    for item in cover["manifests"]["content"]["inventory"]:
        if item["path"] == relative:
            item["sha256"] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            item["size_bytes"] = path.stat().st_size
            break
    _write(artifact / "cover_page.json", cover)
