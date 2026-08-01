"""Portable native-v3 Student-consumption admission and resolution.

This module deliberately resolves the explicit consumption sidecar.  It never
derives a semantic role from a file name or imports RADJAX-Tome or Student.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from radjax_contract.tome.contract_publication import (
    TOME_STUDENT_CONSUMPTION_CONTRACT_ID,
)

PROFILE_ID = "native_v3_student_v1"
_PHASES = (
    "profile_cover",
    "archive_safety",
    "inventory_integrity",
    "binding",
    "encoding",
    "structural_join",
    "corridor",
    "exemplar",
    "provenance",
    "semantic_digest",
)
_REQUIRED_ROLES = {
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
}
_MAX_ARCHIVE_MEMBERS = 100_000
_MAX_MEMBER_BYTES = 64 * 1024**3
_MAX_TOTAL_BYTES = 1024 * 1024**3
_MAX_COMPRESSION_RATIO = 10_000


@dataclass(frozen=True)
class StudentConsumptionIssue:
    code: str
    phase: str
    profile_id: str
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedStudentResource:
    resource_id: str
    role: str
    instance_id: str
    semantic_digest: str
    training_payload_binding: str
    inventory_binding: str
    raw_sha256: str
    raw_size_bytes: int
    encoding: str
    classification: str
    consumption: dict[str, Any]
    locator: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StudentConsumptionDescriptor:
    schema_version: str
    contract_id: str
    profile_id: str
    base_artifact_semantic_digest: str
    consumption_semantic_digest: str
    vocabulary: dict[str, Any]
    sequence: dict[str, Any]
    corridor_resources: tuple[ResolvedStudentResource, ...]
    exemplar_resources: tuple[ResolvedStudentResource, ...]
    validation_resources: tuple[ResolvedStudentResource, ...]
    joins: tuple[dict[str, Any], ...]
    delivery: dict[str, Any]
    provenance: dict[str, Any]
    warnings: tuple[StudentConsumptionIssue, ...]
    nonclaims: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("corridor_resources", "exemplar_resources", "validation_resources"):
            data[key] = [item.to_dict() for item in getattr(self, key)]
        data["warnings"] = [item.to_dict() for item in self.warnings]
        return data


@dataclass(frozen=True)
class StudentConsumptionValidationResult:
    ok: bool
    profile_id: str
    issues: tuple[StudentConsumptionIssue, ...]
    warnings: tuple[StudentConsumptionIssue, ...]
    descriptor: StudentConsumptionDescriptor | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "radjax_student_consumption_validation_result_v1",
            "ok": self.ok,
            "profile_id": self.profile_id,
            "issues": [item.to_dict() for item in self.issues],
            "warnings": [item.to_dict() for item in self.warnings],
            "descriptor": None
            if self.descriptor is None
            else self.descriptor.to_dict(),
        }


def validate_and_resolve_student_consumption(
    artifact: str | Path, *, profile_id: str = PROFILE_ID, strict: bool = False
) -> StudentConsumptionValidationResult:
    """Validate an explicitly extended native-v3 artifact and resolve its roles.

    Archive transport is normalized into a private temporary directory only
    after member safety checks.  C2 currently establishes cover/sidecar,
    inventory, and identity binding; later C2 checks validate resource contents.
    """

    issues: list[StudentConsumptionIssue] = []
    warnings: list[StudentConsumptionIssue] = []
    if profile_id != PROFILE_ID:
        return _result(
            profile_id,
            issues + [_issue("TSC001_PROFILE_UNSUPPORTED", "profile_cover")],
            warnings,
        )
    path = Path(artifact)
    with _artifact_root(path, issues) as root:
        if root is None:
            return _result(profile_id, issues, warnings)
        cover = _read_object(root / "cover_page.json", issues, "profile_cover")
        if cover is None:
            return _result(profile_id, issues, warnings)
        if cover.get("schema_version") == "radjax_tome_cover_v3":
            issues.append(_issue("TSC001_PROFILE_UNSUPPORTED", "profile_cover"))
            return _result(profile_id, issues, warnings)
        if cover.get("schema_version") != "radjax_tome_cover_v3_student_consumption_v1":
            issues.append(_issue("TSC002_COVER_VERSION_UNSUPPORTED", "profile_cover"))
            return _result(profile_id, issues, warnings)
        declared_transport = _nested(cover, "package", "transport")
        actual_transport = "directory" if path.is_dir() else _archive_transport(path)
        if declared_transport != actual_transport:
            issues.append(_issue("TSC020_TRANSPORT_UNSUPPORTED", "profile_cover"))
            return _result(profile_id, issues, warnings)
        sidecar = cover.get("student_consumption")
        content = _nested(cover, "manifests", "content")
        if not isinstance(sidecar, dict) or not isinstance(content, dict):
            issues.append(_issue("TSC013_BINDING_ABSENT", "binding"))
            return _result(profile_id, issues, warnings)
        manifest_path = sidecar.get("manifest_path")
        inventory = content.get("inventory")
        if (
            not isinstance(manifest_path, str)
            or not _safe(manifest_path)
            or not isinstance(inventory, list)
        ):
            issues.append(
                _issue("TSC016_INVENTORY_REFERENCE_INVALID", "inventory_integrity")
            )
            return _result(profile_id, issues, warnings)
        matches = [
            entry
            for entry in inventory
            if isinstance(entry, dict) and entry.get("path") == manifest_path
        ]
        if len(matches) != 1:
            issues.append(
                _issue(
                    "TSC014_BINDING_AMBIGUOUS", "binding", manifest_path=manifest_path
                )
            )
            return _result(profile_id, issues, warnings)
        manifest_file = root / manifest_path
        if not manifest_file.is_file():
            issues.append(
                _issue(
                    "TSC022_RESOURCE_UNAVAILABLE",
                    "inventory_integrity",
                    locator=manifest_path,
                )
            )
            return _result(profile_id, issues, warnings)
        raw_digest = _digest(manifest_file)
        if raw_digest != matches[0].get("sha256") or raw_digest != sidecar.get(
            "manifest_sha256"
        ):
            issues.append(
                _issue(
                    "TSC023_RESOURCE_INTEGRITY_MISMATCH",
                    "inventory_integrity",
                    locator=manifest_path,
                )
            )
            return _result(profile_id, issues, warnings)
        manifest = _read_object(manifest_file, issues, "binding")
        if manifest is None:
            return _result(profile_id, issues, warnings)
        descriptor = _resolve(
            cover, content, manifest, root, profile_id, issues, warnings
        )
        if strict and warnings:
            issues.extend(warnings)
            warnings.clear()
        return _result(profile_id, issues, warnings, descriptor)


def _resolve(
    cover: dict[str, Any],
    content: dict[str, Any],
    manifest: dict[str, Any],
    root: Path,
    profile_id: str,
    issues: list[StudentConsumptionIssue],
    warnings: list[StudentConsumptionIssue],
) -> StudentConsumptionDescriptor | None:
    if (
        manifest.get("profile_id") != profile_id
        or manifest.get("schema_version")
        != "radjax_tome_student_consumption_manifest_v1"
    ):
        issues.append(_issue("TSC001_PROFILE_UNSUPPORTED", "profile_cover"))
        return None
    base = _nested(cover, "identity", "semantic_digest")
    if (
        not isinstance(base, str)
        or manifest.get("base_artifact_semantic_digest") != base
        or content.get("semantic_identity_digest") != base
    ):
        issues.append(_issue("TSC062_BASE_IDENTITY_MISMATCH", "semantic_digest"))
        return None
    identity = manifest.get("semantic_identity")
    resources = manifest.get("resources")
    if not isinstance(identity, dict) or not isinstance(resources, list):
        issues.append(_issue("TSC013_BINDING_ABSENT", "binding"))
        return None
    identity_rows = identity.get("resources")
    if not isinstance(identity_rows, list):
        issues.append(_issue("TSC015_BINDING_INCONSISTENT", "binding"))
        return None
    projection = [
        (
            row.get("resource_id"),
            row.get("role"),
            row.get("instance_id"),
            row.get("semantic_digest"),
        )
        for row in identity_rows
        if isinstance(row, dict)
    ]
    actual = [
        (
            row.get("resource_id"),
            row.get("role"),
            row.get("instance_id"),
            row.get("semantic_digest"),
        )
        for row in resources
        if isinstance(row, dict)
    ]
    if (
        projection != actual
        or len({row[0] for row in actual}) != len(actual)
        or len({row[1:3] for row in actual}) != len(actual)
    ):
        issues.append(_issue("TSC015_BINDING_INCONSISTENT", "binding"))
        return None
    if {row[1] for row in actual} < _REQUIRED_ROLES:
        issues.append(_issue("TSC010_ROLE_MISSING", "binding"))
        return None
    if not _semantic_identity_matches(identity, cover):
        issues.append(_issue("TSC061_CONSUMPTION_DIGEST_MISMATCH", "semantic_digest"))
        return None
    raw_inventory = content.get("inventory", [])
    raw_training = _nested(cover, "identity", "training_payload") or []
    if not isinstance(raw_inventory, list) or not isinstance(raw_training, list):
        issues.append(_issue("TSC013_BINDING_ABSENT", "binding"))
        return None
    inventory_paths = [
        entry.get("path") for entry in raw_inventory if isinstance(entry, dict)
    ]
    logical_ids = [
        entry.get("logical_id") for entry in raw_training if isinstance(entry, dict)
    ]
    if (
        len(inventory_paths) != len(raw_inventory)
        or len(set(inventory_paths)) != len(inventory_paths)
        or len(logical_ids) != len(raw_training)
        or len(set(logical_ids)) != len(logical_ids)
    ):
        issues.append(_issue("TSC014_BINDING_AMBIGUOUS", "binding"))
        return None
    inventory = {
        entry.get("path"): entry for entry in raw_inventory if isinstance(entry, dict)
    }
    training = {
        entry.get("logical_id"): entry
        for entry in raw_training
        if isinstance(entry, dict)
    }
    resolved: list[ResolvedStudentResource] = []
    for row in resources:
        if not isinstance(row, dict):
            issues.append(_issue("TSC013_BINDING_ABSENT", "binding"))
            continue
        logical = row.get("training_payload_binding")
        locator = row.get("inventory_binding")
        if (
            logical not in training
            or locator not in inventory
            or not isinstance(locator, str)
            or not _safe(locator)
        ):
            issues.append(
                _issue(
                    "TSC016_INVENTORY_REFERENCE_INVALID",
                    "binding",
                    resource_id=row.get("resource_id"),
                )
            )
            continue
        if training[logical].get("semantic_digest") != row.get("semantic_digest"):
            issues.append(
                _issue(
                    "TSC015_BINDING_INCONSISTENT",
                    "binding",
                    resource_id=row.get("resource_id"),
                )
            )
            continue
        file = root / locator
        if (
            not file.is_file()
            or _digest(file) != inventory[locator].get("sha256")
            or file.stat().st_size != inventory[locator].get("size_bytes")
        ):
            issues.append(
                _issue(
                    "TSC023_RESOURCE_INTEGRITY_MISMATCH",
                    "inventory_integrity",
                    resource_id=row.get("resource_id"),
                )
            )
            continue
        resolved.append(
            ResolvedStudentResource(
                row["resource_id"],
                row["role"],
                row["instance_id"],
                row["semantic_digest"],
                logical,
                locator,
                inventory[locator]["sha256"],
                inventory[locator].get("size_bytes", -1),
                row["encoding"],
                row["classification"],
                dict(row["consumption"]),
                locator,
            )
        )
    if issues:
        return None

    def group(names: set[str]) -> tuple[ResolvedStudentResource, ...]:
        return tuple(item for item in resolved if item.role in names)

    return StudentConsumptionDescriptor(
        "radjax_student_consumption_descriptor_v1",
        TOME_STUDENT_CONSUMPTION_CONTRACT_ID,
        profile_id,
        base,
        identity.get("semantic_digest", ""),
        dict(identity.get("vocabulary", {})),
        dict(identity.get("sequence", {})),
        group(
            {
                "target_shard",
                "example_registry",
                "corridor_mode_table",
                "corridor_assignment",
            }
        ),
        group({"selected_passport_index", "selected_exemplar_payload"}),
        group(
            {
                "corridor_observed_statistics",
                "row_range_declaration",
                "delivery_receipt",
                "authority_reference",
            }
        ),
        tuple(manifest.get("joins", [])),
        {"transport": _nested(cover, "package", "transport")},
        dict(manifest.get("provenance", {})),
        tuple(warnings),
        ("not_a_student_loader", "not_a_training_policy"),
    )


def _artifact_root(path: Path, issues: list[StudentConsumptionIssue]):
    if path.is_dir():
        return _temporary_root(path)
    if not path.is_file():
        issues.append(_issue("TSC020_TRANSPORT_UNSUPPORTED", "archive_safety"))
        return _temporary_root(None)
    return _safe_archive_root(path, issues)


class _temporary_root:
    def __init__(self, root: Path | None):
        self.root = root

    def __enter__(self) -> Path | None:
        return self.root

    def __exit__(self, *_: object) -> None:
        return None


class _safe_archive_root:
    def __init__(self, path: Path, issues: list[StudentConsumptionIssue]):
        self.path, self.issues, self.temp = (
            path,
            issues,
            tempfile.TemporaryDirectory(prefix="radjax-tsc-"),
        )

    def __enter__(self) -> Path | None:
        root = Path(self.temp.name)
        try:
            with tarfile.open(self.path, "r:*") as archive:
                names: set[str] = set()
                total = 0
                count = 0
                for member in archive:
                    count += 1
                    total += member.size
                    if (
                        count > _MAX_ARCHIVE_MEMBERS
                        or member.size < 0
                        or member.size > _MAX_MEMBER_BYTES
                        or total > _MAX_TOTAL_BYTES
                        or not member.isfile()
                        or not _safe(member.name)
                        or member.name in names
                    ):
                        raise ValueError
                    names.add(member.name)
                    compressed = max(self.path.stat().st_size, 1)
                    if total / compressed > _MAX_COMPRESSION_RATIO:
                        raise ValueError
                    target = root / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = archive.extractfile(member)
                    if source is None:
                        raise ValueError
                    target.write_bytes(source.read())
            return root
        except (OSError, tarfile.TarError, ValueError):
            self.issues.append(_issue("TSC021_TRANSPORT_UNSAFE", "archive_safety"))
            return None

    def __exit__(self, *_: object) -> None:
        self.temp.cleanup()


def _read_object(
    path: Path, issues: list[StudentConsumptionIssue], phase: str
) -> dict[str, Any] | None:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        issues.append(_issue("TSC060_CONSUMPTION_CANONICALIZATION", phase))
        return None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _safe(value: str) -> bool:
    pure = PurePosixPath(value)
    return (
        bool(value)
        and not pure.is_absolute()
        and ".." not in pure.parts
        and pure.as_posix() == value
    )


def _archive_transport(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            header = handle.read(2)
    except OSError:
        return "unknown"
    return "tgz" if header == b"\x1f\x8b" else "rtome"


def _nested(value: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _semantic_identity_matches(identity: dict[str, Any], cover: dict[str, Any]) -> bool:
    """Validate the C1 canonical semantic projection without hashing locators."""

    digest = identity.get("semantic_digest")
    sidecar = cover.get("student_consumption")
    if not isinstance(digest, str) or not isinstance(sidecar, dict):
        return False
    projection = {
        key: value for key, value in identity.items() if key != "semantic_digest"
    }
    try:
        encoded = json.dumps(
            projection,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return False
    expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
    return digest == expected and sidecar.get("semantic_digest") == expected


def _issue(code: str, phase: str, **context: Any) -> StudentConsumptionIssue:
    return StudentConsumptionIssue(code, phase, PROFILE_ID, context)


def _result(
    profile_id: str,
    issues: list[StudentConsumptionIssue],
    warnings: list[StudentConsumptionIssue],
    descriptor: StudentConsumptionDescriptor | None = None,
) -> StudentConsumptionValidationResult:
    order = {phase: index for index, phase in enumerate(_PHASES)}
    ordered = tuple(
        sorted(
            issues,
            key=lambda item: (
                order[item.phase],
                str(item.context.get("resource_id", "")),
                item.code,
            ),
        )
    )
    return StudentConsumptionValidationResult(
        not ordered,
        profile_id,
        ordered,
        tuple(warnings),
        None if ordered else descriptor,
    )
