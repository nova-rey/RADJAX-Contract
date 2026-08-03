"""Strict public opening for admitted v6 multipart components."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from radjax_contract.tome import (
    VerifiedStudentResourceComponentV6,
    open_verified_student_resource_component_v6,
    validate_and_resolve_student_consumption_v6,
)
from radjax_contract.tome import student_consumption as v1_module
from radjax_contract.tome import student_consumption_v6 as v6_module
from tests.test_student_consumption_v6_identity import _v6_package
from tests.test_student_language_binding_v6_projection import (
    _canonical_archive,
    _unsafe_archive,
)


def _target_resource(package: Path):
    admitted = validate_and_resolve_student_consumption_v6(package, strict=True)
    assert admitted.ok and admitted.descriptor is not None
    return next(
        resource
        for resource in admitted.descriptor.authority_resources
        if resource.resource_id == "target_shard/default"
    )


def test_v6_target_components_open_identically_from_directory_and_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _v6_package(tmp_path / "directory")
    archive = _canonical_archive(package, tmp_path / "student.tgz")
    target = _target_resource(package)
    admissions = 0
    original = v6_module.validate_and_resolve_student_consumption_v6

    def counted(*args: object, **kwargs: object) -> object:
        nonlocal admissions
        admissions += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        v6_module, "validate_and_resolve_student_consumption_v6", counted
    )
    for declaration in target.components:
        component_id = declaration["component"]
        with open_verified_student_resource_component_v6(
            package, target.resource_id, component_id
        ) as directory:
            assert isinstance(directory, VerifiedStudentResourceComponentV6)
            assert directory.content.writable() is False
            directory_bytes = directory.content.read()
            directory.content.seek(0)
            decoded = np.load(directory.content, allow_pickle=False)
            assert decoded.ndim == len(directory.axes)
            stream = directory.content
        assert stream.closed
        with open_verified_student_resource_component_v6(
            archive, target.resource_id, component_id
        ) as archived:
            archive_bytes = archived.content.read()
            assert archived.to_dict() == directory.to_dict()
            assert archived.resource_semantic_identity == target.semantic_identity
            assert archived.raw_sha256 == declaration["raw_sha256"]
            assert archived.raw_size_bytes == declaration["raw_size_bytes"]
            assert len(archive_bytes) == archived.raw_size_bytes
            assert "locator" not in archived.to_dict()
            assert "content" not in archived.to_dict()
        assert archive_bytes == directory_bytes
    assert admissions == 2 * len(target.components)


@pytest.mark.parametrize(
    ("resource_id", "component_id", "message"),
    [
        ("missing/default", "input_ids", "unknown v6 behavioral resource"),
        (
            "target_shard/default",
            "missing",
            "unknown component",
        ),
        (
            "corridor_assignment/default",
            "input_ids",
            "unknown component",
        ),
        (
            "example_registry/default",
            "input_ids",
            "requires a multipart resource",
        ),
    ],
)
def test_v6_component_opener_rejects_unknown_and_mismatched_declarations(
    tmp_path: Path,
    resource_id: str,
    component_id: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        with open_verified_student_resource_component_v6(
            _v6_package(tmp_path), resource_id, component_id
        ):
            pass


@pytest.mark.parametrize(
    "profile_id",
    ["native_v3_student_v5", "native_v3_student_v4", "unknown_profile"],
)
def test_v6_component_opener_rejects_historical_profiles_and_non_strict_use(
    tmp_path: Path, profile_id: str
) -> None:
    with pytest.raises(ValueError, match="unsupported component opener profile"):
        with open_verified_student_resource_component_v6(
            tmp_path,
            "target_shard/default",
            "input_ids",
            profile_id=profile_id,
        ):
            pass
    with pytest.raises(ValueError, match="requires strict admission"):
        with open_verified_student_resource_component_v6(
            tmp_path,
            "target_shard/default",
            "input_ids",
            strict=False,
        ):
            pass


@pytest.mark.parametrize("mutation", ["locator", "size", "bytes"])
def test_v6_component_opener_rejects_locator_size_and_byte_tampering(
    tmp_path: Path, mutation: str
) -> None:
    package = _v6_package(tmp_path)
    manifest_path = package / "manifests/behavioral_resource_binding_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = next(
        resource
        for resource in manifest["resources"]
        if resource["resource_id"] == "target_shard/default"
    )
    components = {item["component"]: item for item in target["components"]}
    selected = components["input_ids"]
    if mutation == "locator":
        selected["locator"] = components["attention_mask"]["locator"]
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    elif mutation == "size":
        selected["raw_size_bytes"] += 1
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    else:
        path = package / selected["locator"]
        path.write_bytes(path.read_bytes() + b"tamper")

    with pytest.raises(ValueError, match="BRC010_RAW_INTEGRITY_MISMATCH"):
        with open_verified_student_resource_component_v6(
            package, "target_shard/default", "input_ids"
        ):
            pass


def test_v6_component_opener_rejects_rehashed_cross_resource_substitution(
    tmp_path: Path,
) -> None:
    package = _v6_package(tmp_path)
    manifest_path = package / "manifests/behavioral_resource_binding_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_resource = {item["resource_id"]: item for item in manifest["resources"]}
    target = by_resource["target_shard/default"]
    assignment = by_resource["corridor_assignment/default"]
    selected = next(
        item for item in target["components"] if item["component"] == "input_ids"
    )
    substitute = next(
        item for item in assignment["components"] if item["component"] == "mode_id"
    )
    selected.update(
        {
            key: substitute[key]
            for key in ("locator", "axes", "raw_sha256", "raw_size_bytes")
        }
    )
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="BRC011_RESOURCE_SEMANTIC_MISMATCH"):
        with open_verified_student_resource_component_v6(
            package, "target_shard/default", "input_ids"
        ):
            pass


def test_v6_component_opener_rechecks_after_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _v6_package(tmp_path)
    target = _target_resource(package)
    declaration = next(
        item for item in target.components if item["component"] == "input_ids"
    )
    component_path = package / declaration["locator"]
    original = v6_module.validate_and_resolve_student_consumption_v6

    def replace_after_admission(*args: object, **kwargs: object) -> object:
        result = original(*args, **kwargs)
        component_path.write_bytes(component_path.read_bytes() + b"replacement")
        return result

    monkeypatch.setattr(
        v6_module,
        "validate_and_resolve_student_consumption_v6",
        replace_after_admission,
    )
    with pytest.raises(ValueError, match="component integrity changed at open"):
        with open_verified_student_resource_component_v6(
            package, target.resource_id, "input_ids"
        ):
            pass


@pytest.mark.parametrize("mutation", ["traversal", "duplicate", "symbolic_link"])
def test_v6_component_opener_inherits_archive_safety(
    tmp_path: Path, mutation: str
) -> None:
    archive = _unsafe_archive(tmp_path / f"{mutation}.tgz", mutation)
    with pytest.raises(ValueError, match="BRC001_ARTIFACT_UNAVAILABLE"):
        with open_verified_student_resource_component_v6(
            archive, "target_shard/default", "input_ids"
        ):
            pass


@pytest.mark.parametrize(
    "limit",
    [
        "_MAX_ARCHIVE_MEMBERS",
        "_MAX_MEMBER_BYTES",
        "_MAX_TOTAL_BYTES",
        "_MAX_COMPRESSION_RATIO",
    ],
)
def test_v6_component_opener_inherits_archive_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    package = _v6_package(tmp_path / "directory")
    archive = _canonical_archive(package, tmp_path / "student.tgz")
    monkeypatch.setattr(v1_module, limit, 1)
    with pytest.raises(ValueError, match="BRC001_ARTIFACT_UNAVAILABLE"):
        with open_verified_student_resource_component_v6(
            archive, "target_shard/default", "input_ids"
        ):
            pass
