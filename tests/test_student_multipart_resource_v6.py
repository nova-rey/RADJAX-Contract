"""Aggregate strict opening for complete v6 multipart resources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from radjax_contract.tome import (
    VerifiedStudentMultipartComponentV6,
    VerifiedStudentMultipartResourceV6,
    open_verified_student_multipart_resource_v6,
)
from radjax_contract.tome import student_consumption as v1_module
from radjax_contract.tome import student_consumption_v6 as v6_module
from tests.test_student_consumption_v6_identity import _v6_package
from tests.test_student_language_binding_v6_projection import (
    _canonical_archive,
    _unsafe_archive,
)


def _read_multipart(artifact: Path, resource_id: str):
    with open_verified_student_multipart_resource_v6(artifact, resource_id) as resource:
        assert isinstance(resource, VerifiedStudentMultipartResourceV6)
        metadata = resource.to_dict()
        payloads: dict[str, bytes] = {}
        streams = []
        for component_id, component in resource.components.items():
            assert isinstance(component, VerifiedStudentMultipartComponentV6)
            assert component_id == component.component_id
            assert component.content.writable() is False
            payload = component.content.read()
            payloads[component_id] = payload
            component.content.seek(0)
            array = np.load(component.content, allow_pickle=False)
            assert component.encoding == "npy"
            assert component.dtype == array.dtype.str
            assert component.shape == array.shape
            assert len(component.axes) == array.ndim
            assert component.raw_size_bytes == len(payload)
            assert component.raw_sha256 == (
                "sha256:" + hashlib.sha256(payload).hexdigest()
            )
            streams.append(component.content)
        with pytest.raises(KeyError):
            resource.components["not_declared"]
        with pytest.raises(TypeError):
            resource.components["not_declared"] = next(
                iter(resource.components.values())
            )
        serialized = json.dumps(metadata, sort_keys=True)
        assert "locator" not in serialized
        assert "radjax-tsc-" not in serialized
    assert all(stream.closed for stream in streams)
    return metadata, payloads


@pytest.mark.parametrize(
    ("resource_id", "expected_components"),
    [
        ("target_shard/default", {"attention_mask", "input_ids"}),
        (
            "corridor_assignment/default",
            {"example_index", "mode_id", "position", "weight"},
        ),
    ],
)
def test_v6_multipart_directory_and_archive_objects_are_identical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    resource_id: str,
    expected_components: set[str],
) -> None:
    package = _v6_package(tmp_path / "directory")
    archive = _canonical_archive(package, tmp_path / "student.tgz")
    admissions = 0
    original = v6_module.validate_and_resolve_student_consumption_v6

    def counted(*args: object, **kwargs: object) -> object:
        nonlocal admissions
        admissions += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        v6_module, "validate_and_resolve_student_consumption_v6", counted
    )
    directory_metadata, directory_payloads = _read_multipart(package, resource_id)
    archive_metadata, archive_payloads = _read_multipart(archive, resource_id)

    assert admissions == 2
    assert set(directory_metadata["components"]) == expected_components
    assert archive_metadata == directory_metadata
    assert archive_payloads == directory_payloads


@pytest.mark.parametrize(
    ("resource_id", "message"),
    [
        ("missing/default", "unknown v6 behavioral resource"),
        ("example_registry/default", "requires a multipart resource"),
    ],
)
def test_v6_multipart_opener_rejects_unknown_and_non_multipart_resources(
    tmp_path: Path, resource_id: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        with open_verified_student_multipart_resource_v6(
            _v6_package(tmp_path), resource_id
        ):
            pass


@pytest.mark.parametrize(
    "profile_id",
    ["native_v3_student_v5", "native_v3_student_v4", "unknown_profile"],
)
def test_v6_multipart_opener_rejects_historical_profiles_and_non_strict_use(
    tmp_path: Path, profile_id: str
) -> None:
    with pytest.raises(ValueError, match="unsupported multipart opener profile"):
        with open_verified_student_multipart_resource_v6(
            tmp_path, "target_shard/default", profile_id=profile_id
        ):
            pass
    with pytest.raises(ValueError, match="requires strict admission"):
        with open_verified_student_multipart_resource_v6(
            tmp_path, "target_shard/default", strict=False
        ):
            pass


def test_v6_multipart_opener_rejects_component_tampering(tmp_path: Path) -> None:
    package = _v6_package(tmp_path)
    manifest_path = package / "manifests/behavioral_resource_binding_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = next(
        resource
        for resource in manifest["resources"]
        if resource["resource_id"] == "target_shard/default"
    )
    component = next(
        item for item in target["components"] if item["component"] == "input_ids"
    )
    path = package / component["locator"]
    path.write_bytes(path.read_bytes() + b"tamper")

    with pytest.raises(ValueError, match="BRC010_RAW_INTEGRITY_MISMATCH"):
        with open_verified_student_multipart_resource_v6(
            package, "target_shard/default"
        ):
            pass


def test_v6_multipart_opener_rejects_cross_resource_substitution(
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
        with open_verified_student_multipart_resource_v6(
            package, "target_shard/default"
        ):
            pass


def test_v6_multipart_opener_rechecks_every_component_after_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _v6_package(tmp_path)
    component_path = package / "resources/target_shard.input_ids.npy"
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
        with open_verified_student_multipart_resource_v6(
            package, "target_shard/default"
        ):
            pass


@pytest.mark.parametrize("mutation", ["traversal", "duplicate", "symbolic_link"])
def test_v6_multipart_opener_inherits_archive_safety(
    tmp_path: Path, mutation: str
) -> None:
    archive = _unsafe_archive(tmp_path / f"{mutation}.tgz", mutation)
    with pytest.raises(ValueError, match="BRC001_ARTIFACT_UNAVAILABLE"):
        with open_verified_student_multipart_resource_v6(
            archive, "target_shard/default"
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
def test_v6_multipart_opener_inherits_archive_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    package = _v6_package(tmp_path / "directory")
    archive = _canonical_archive(package, tmp_path / "student.tgz")
    monkeypatch.setattr(v1_module, limit, 1)
    with pytest.raises(ValueError, match="BRC001_ARTIFACT_UNAVAILABLE"):
        with open_verified_student_multipart_resource_v6(
            archive, "target_shard/default"
        ):
            pass
