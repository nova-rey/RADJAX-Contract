"""Public v6-bound language/tokenizer projection conformance."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import replace
from gzip import GzipFile
from pathlib import Path, PurePosixPath

import pytest

from radjax_contract.tome import (
    LanguageTokenizerBindingDescriptor,
    resolve_student_language_binding,
    validate_and_resolve_student_consumption,
)
from radjax_contract.tome import student_consumption as v1_module
from radjax_contract.tome import student_consumption_v6 as v6_module
from tests.test_student_consumption_v6_identity import _identity, _v6_package


def _canonical_archive(root: Path, destination: Path) -> Path:
    with destination.open("wb") as raw:
        with GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gzip:
            with tarfile.open(fileobj=gzip, mode="w") as archive:
                for path in sorted(item for item in root.rglob("*") if item.is_file()):
                    payload = path.read_bytes()
                    member = tarfile.TarInfo(path.relative_to(root).as_posix())
                    member.size = len(payload)
                    member.mtime = 0
                    member.uid = member.gid = 0
                    member.uname = member.gname = ""
                    member.mode = 0o644
                    archive.addfile(member, io.BytesIO(payload))
    return destination


def _unsafe_archive(destination: Path, mutation: str) -> Path:
    with tarfile.open(destination, "w:gz") as archive:
        if mutation == "traversal":
            member = tarfile.TarInfo("../outside")
            member.size = 1
            archive.addfile(member, io.BytesIO(b"x"))
        elif mutation == "duplicate":
            for _ in range(2):
                member = tarfile.TarInfo("duplicate")
                member.size = 1
                archive.addfile(member, io.BytesIO(b"x"))
        else:
            member = tarfile.TarInfo("unsafe-link")
            member.type = tarfile.SYMTYPE
            member.linkname = "outside"
            archive.addfile(member)
    return destination


def test_v6_directory_and_archive_return_identical_typed_language_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    directory = resolve_student_language_binding(package)
    assert admissions == 1
    archived = resolve_student_language_binding(archive)
    assert admissions == 2

    assert isinstance(directory, LanguageTokenizerBindingDescriptor)
    assert archived == directory
    for artifact, language in ((package, directory), (archive, archived)):
        admitted = validate_and_resolve_student_consumption(
            artifact, profile_id="native_v3_student_v6", strict=True
        )
        assert admitted.ok and admitted.descriptor is not None
        assert (
            language.canonical_binding_digest
            == admitted.descriptor.language_binding_digest
        )
    for resource in archived.resources:
        assert not PurePosixPath(resource.locator).is_absolute()
        assert "radjax-tsc-" not in resource.locator
        assert str(archive) not in resource.locator


def test_v6_projection_rejects_tampered_embedded_language_binding(
    tmp_path: Path,
) -> None:
    package = _v6_package(tmp_path)
    binding_path = package / "manifests/language_tokenizer_binding_v1.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["canonical_binding_digest"] = _identity("0")
    binding_path.write_text(json.dumps(binding, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="BRC002_LANGUAGE_BINDING_INVALID"):
        resolve_student_language_binding(package)


def test_v6_projection_rejects_mismatched_admission_language_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    admitted = v6_module.validate_and_resolve_student_consumption_v6(
        _v6_package(tmp_path), strict=True
    )
    assert admitted.ok and admitted.descriptor is not None
    tampered = replace(
        admitted,
        descriptor=replace(admitted.descriptor, language_binding_digest=_identity("0")),
    )
    monkeypatch.setattr(
        v6_module,
        "validate_and_resolve_student_consumption_v6",
        lambda *args, **kwargs: tampered,
    )

    with pytest.raises(ValueError, match="digest mismatch"):
        resolve_student_language_binding(tmp_path)


@pytest.mark.parametrize(
    "profile_id",
    ["native_v3_student_v5", "native_v3_student_v4", "unknown_profile"],
)
def test_v6_projection_rejects_wrong_and_historical_profiles(
    tmp_path: Path, profile_id: str
) -> None:
    with pytest.raises(ValueError, match="unsupported language projection profile"):
        resolve_student_language_binding(tmp_path, profile_id=profile_id)
    with pytest.raises(ValueError, match="requires strict admission"):
        resolve_student_language_binding(
            tmp_path, profile_id="native_v3_student_v6", strict=False
        )


@pytest.mark.parametrize("mutation", ["traversal", "duplicate", "symbolic_link"])
def test_v6_projection_preserves_unsafe_archive_rejection(
    tmp_path: Path, mutation: str
) -> None:
    archive = _unsafe_archive(tmp_path / f"{mutation}.tgz", mutation)
    with pytest.raises(ValueError, match="BRC001_ARTIFACT_UNAVAILABLE"):
        resolve_student_language_binding(archive)


@pytest.mark.parametrize(
    ("limit", "value"),
    [
        ("_MAX_ARCHIVE_MEMBERS", 1),
        ("_MAX_MEMBER_BYTES", 1),
        ("_MAX_TOTAL_BYTES", 1),
        ("_MAX_COMPRESSION_RATIO", 1),
    ],
)
def test_v6_projection_preserves_archive_size_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit: str,
    value: int,
) -> None:
    package = _v6_package(tmp_path / "directory")
    archive = _canonical_archive(package, tmp_path / "student.tgz")
    monkeypatch.setattr(v1_module, limit, value)
    with pytest.raises(ValueError, match="BRC001_ARTIFACT_UNAVAILABLE"):
        resolve_student_language_binding(archive)


def test_v6_projection_is_public_in_built_wheel(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(tmp_path),
            ".",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(tmp_path.glob("radjax_contract-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        assert "radjax_contract/tome/student_consumption_v6.py" in archive.namelist()
    installed = tmp_path / "installed"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(installed),
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(installed)
    environment["RADJAX_EXPECTED_INSTALL"] = str(installed)
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; from pathlib import Path; import radjax_contract.tome as tome; "
            "from radjax_contract.tome import ("
            "LanguageTokenizerBindingDescriptor, "
            "VerifiedStudentResourceComponentV6, "
            "open_verified_student_resource_component_v6, "
            "resolve_student_language_binding); "
            "assert callable(resolve_student_language_binding); "
            "assert callable(open_verified_student_resource_component_v6); "
            "assert VerifiedStudentResourceComponentV6.__module__.startswith("
            "'radjax_contract'); "
            "assert LanguageTokenizerBindingDescriptor.__module__.startswith("
            "'radjax_contract'); "
            "assert Path(tome.__file__).is_relative_to("
            "Path(os.environ['RADJAX_EXPECTED_INSTALL']))",
        ],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
