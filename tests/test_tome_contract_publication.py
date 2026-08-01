from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from radjax_contract.tome import (
    TOME_CONTRACT_ID,
    TOME_CONTRACT_PUBLICATION_VERSION,
    TOME_STREAMING_CONTRACT_PUBLICATION_VERSION,
    TOME_STUDENT_CONSUMPTION_CONTRACT_ID,
    TOME_STUDENT_CONSUMPTION_CONTRACT_PUBLICATION_VERSION,
    open_streaming_tome,
    tome_contract_asset_path,
    tome_contract_root,
    tome_streaming_contract_asset_path,
    tome_streaming_contract_root,
    tome_student_consumption_contract_asset_path,
    tome_student_consumption_contract_root,
    validate_and_resolve_student_consumption,
    validate_streaming_tome,
)


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
