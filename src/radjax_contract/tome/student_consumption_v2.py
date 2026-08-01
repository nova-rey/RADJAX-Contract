"""Portable resolution for independently digested native-v3 sidecars.

V2 deliberately separates the immutable native-v3 base semantic digest from
the semantic digests of derived Student-consumption resources.  It is not a
fallback for the published V1 profile and never infers roles from paths.
"""

from __future__ import annotations

import hashlib
import json
import struct
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from radjax_contract.tome import student_consumption as _v1
from radjax_contract.tome.contract_publication import (
    tome_student_consumption_v2_contract_root,
)
from radjax_contract.tome.student_consumption_corridor import (
    validate_corridor_resources,
)
from radjax_contract.tome.student_exemplar_semantics import (
    validate_exemplar_passport_semantics,
)

PROFILE_ID = "native_v3_student_v2"
CONTRACT_ID = "radjax_tome_student_consumption_contract"
_MANIFEST_PATH = "manifests/student_consumption_v2.json"
_ROLE_ORDER = _v1._ROLE_ORDER
_REQUIRED_ROLES = _v1._REQUIRED_ROLES
_ROLE_CLASSIFICATIONS = _v1._ROLE_CLASSIFICATIONS
_REQUIRED_JOINS = _v1._REQUIRED_JOINS
_PHASES = _v1._PHASES


def contract_root() -> Path:
    """Return the installed V2 Student-consumption Contract assets."""

    return tome_student_consumption_v2_contract_root()


@dataclass(frozen=True)
class ResolvedStudentConsumptionV2Resource:
    resource_id: str
    role: str
    instance_id: str
    semantic_digest: str
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
class StudentConsumptionV2Descriptor:
    schema_version: str
    contract_id: str
    profile_id: str
    base_artifact_semantic_digest: str
    consumption_semantic_digest: str
    vocabulary: dict[str, Any]
    sequence: dict[str, Any]
    corridor_resources: tuple[ResolvedStudentConsumptionV2Resource, ...]
    exemplar_resources: tuple[ResolvedStudentConsumptionV2Resource, ...]
    validation_resources: tuple[ResolvedStudentConsumptionV2Resource, ...]
    joins: tuple[dict[str, Any], ...]
    delivery: dict[str, Any]
    provenance: dict[str, Any]
    warnings: tuple[_v1.StudentConsumptionIssue, ...]
    nonclaims: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("corridor_resources", "exemplar_resources", "validation_resources"):
            data[key] = [item.to_dict() for item in getattr(self, key)]
        data["joins"] = list(self.joins)
        data["warnings"] = [item.to_dict() for item in self.warnings]
        data["nonclaims"] = list(self.nonclaims)
        return data


@dataclass(frozen=True)
class StudentConsumptionV2ValidationResult:
    ok: bool
    profile_id: str
    issues: tuple[_v1.StudentConsumptionIssue, ...]
    warnings: tuple[_v1.StudentConsumptionIssue, ...]
    descriptor: StudentConsumptionV2Descriptor | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "radjax_student_consumption_validation_result_v2",
            "ok": self.ok,
            "profile_id": self.profile_id,
            "issues": [item.to_dict() for item in self.issues],
            "warnings": [item.to_dict() for item in self.warnings],
            "descriptor": None
            if self.descriptor is None
            else self.descriptor.to_dict(),
        }


def validate_and_resolve_student_consumption_v2(
    artifact: str | Path, *, strict: bool = False
) -> StudentConsumptionV2ValidationResult:
    """Validate and resolve the additive V2 native-v3 consumption profile."""

    issues: list[_v1.StudentConsumptionIssue] = []
    warnings: list[_v1.StudentConsumptionIssue] = []
    path = Path(artifact)
    # Reuse the mature archive safety implementation, then normalize profile
    # on any resulting transport issue at our public boundary.
    with _v1._artifact_root(path, issues, warnings) as root:
        _reprofile(issues)
        _reprofile(warnings)
        if root is None:
            return _result(issues, warnings)
        cover = _read_object(root / "cover_page.json", issues, "profile_cover")
        if cover is None:
            return _result(issues, warnings)
        if cover.get("schema_version") == "radjax_tome_cover_v3":
            issues.append(_issue("TSC001_PROFILE_UNSUPPORTED", "profile_cover"))
            return _result(issues, warnings)
        if cover.get("schema_version") != "radjax_tome_cover_v3_student_consumption_v2":
            issues.append(_issue("TSC002_COVER_VERSION_UNSUPPORTED", "profile_cover"))
            return _result(issues, warnings)
        if not _validate_cover(cover):
            issues.append(_issue("TSC002_COVER_VERSION_UNSUPPORTED", "profile_cover"))
            return _result(issues, warnings)
        actual_transport = (
            "directory" if path.is_dir() else _v1._archive_transport(path)
        )
        if _v1._nested(cover, "package", "transport") != actual_transport:
            issues.append(_issue("TSC020_TRANSPORT_UNSUPPORTED", "profile_cover"))
            return _result(issues, warnings)
        sidecar = cover.get("student_consumption")
        content = _v1._nested(cover, "manifests", "content")
        if not isinstance(sidecar, dict) or not isinstance(content, dict):
            issues.append(_issue("TSC013_INVENTORY_BINDING_ABSENT", "binding"))
            return _result(issues, warnings)
        if sidecar.get("profile_id") != PROFILE_ID:
            issues.append(_issue("TSC001_PROFILE_UNSUPPORTED", "profile_cover"))
            return _result(issues, warnings)
        manifest_path = sidecar.get("manifest_path")
        inventory = content.get("inventory")
        if manifest_path != _MANIFEST_PATH or not isinstance(inventory, list):
            issues.append(
                _issue("TSC016_INVENTORY_REFERENCE_INVALID", "inventory_integrity")
            )
            return _result(issues, warnings)
        matches = [
            item
            for item in inventory
            if isinstance(item, dict) and item.get("path") == manifest_path
        ]
        if len(matches) != 1 or not _v1._safe(manifest_path):
            issues.append(
                _issue(
                    "TSC014_INVENTORY_BINDING_AMBIGUOUS",
                    "binding",
                    manifest_path=manifest_path,
                )
            )
            return _result(issues, warnings)
        manifest_file = root / manifest_path
        if not manifest_file.is_file():
            issues.append(
                _issue(
                    "TSC022_RESOURCE_UNAVAILABLE",
                    "inventory_integrity",
                    locator=manifest_path,
                )
            )
            return _result(issues, warnings)
        digest = _v1._digest(manifest_file)
        if digest != matches[0].get("sha256") or digest != sidecar.get(
            "manifest_sha256"
        ):
            issues.append(
                _issue(
                    "TSC023_RESOURCE_INTEGRITY_MISMATCH",
                    "inventory_integrity",
                    locator=manifest_path,
                )
            )
            return _result(issues, warnings)
        manifest = _read_object(manifest_file, issues, "binding")
        if manifest is None or not _validate_manifest(manifest):
            issues.append(_issue("TSC013_INVENTORY_BINDING_ABSENT", "binding"))
            return _result(issues, warnings)
        descriptor = _resolve(cover, content, manifest, root, issues, warnings)
        if strict and warnings:
            issues.extend(warnings)
            warnings.clear()
        return _result(issues, warnings, descriptor)


@contextmanager
def open_verified_student_resource_v2(
    artifact: str | Path, resource_id: str, *, strict: bool = False
):
    """Open one V2 logical resource after admission, with deterministic cleanup."""

    result = validate_and_resolve_student_consumption_v2(artifact, strict=strict)
    if not result.ok or result.descriptor is None:
        raise ValueError(
            "Student-consumption validation failed: "
            + ",".join(item.code for item in result.issues)
        )
    resources = (
        result.descriptor.corridor_resources
        + result.descriptor.exemplar_resources
        + result.descriptor.validation_resources
    )
    resource = next(
        (item for item in resources if item.resource_id == resource_id), None
    )
    if resource is None:
        raise ValueError(f"unknown Student-consumption resource: {resource_id}")
    with _v1._artifact_root(Path(artifact), [], []) as root:
        if root is None:
            raise ValueError("Student-consumption resource transport is unavailable")
        path = root / resource.locator
        if (
            not path.is_file()
            or path.stat().st_size != resource.raw_size_bytes
            or _v1._digest(path) != resource.raw_sha256
        ):
            raise ValueError("Student-consumption resource integrity changed at open")
        with path.open("rb") as handle:
            yield handle


def _resolve(
    cover: dict[str, Any],
    content: dict[str, Any],
    manifest: dict[str, Any],
    root: Path,
    issues: list[_v1.StudentConsumptionIssue],
    warnings: list[_v1.StudentConsumptionIssue],
) -> StudentConsumptionV2Descriptor | None:
    if (
        manifest.get("profile_id") != PROFILE_ID
        or manifest.get("schema_version")
        != "radjax_tome_student_consumption_manifest_v2"
    ):
        issues.append(_issue("TSC001_PROFILE_UNSUPPORTED", "profile_cover"))
        return None
    base = _v1._nested(cover, "identity", "semantic_digest")
    if (
        not isinstance(base, str)
        or manifest.get("base_artifact_semantic_digest") != base
        or content.get("semantic_identity_digest") != base
    ):
        issues.append(_issue("TSC062_BASE_IDENTITY_MISMATCH", "semantic_digest"))
        return None
    identity = manifest.get("semantic_identity")
    rows = manifest.get("resources")
    if not isinstance(identity, dict) or not isinstance(rows, list):
        issues.append(_issue("TSC013_INVENTORY_BINDING_ABSENT", "binding"))
        return None
    projection = _resource_projection(identity.get("resources"))
    actual = _resource_projection(rows)
    if projection is None or actual is None or projection != actual:
        issues.append(_issue("TSC015_DERIVED_SEMANTIC_INCONSISTENT", "binding"))
        return None
    if len({row[0] for row in actual}) != len(actual) or len(
        {row[1:3] for row in actual}
    ) != len(actual):
        issues.append(_issue("TSC011_ROLE_DUPLICATE", "binding"))
        return None
    rank = {role: position for position, role in enumerate(_ROLE_ORDER)}
    if actual != sorted(
        actual, key=lambda row: (rank.get(row[1], len(rank)), row[2], row[0])
    ):
        issues.append(_issue("TSC012_ROLE_INSTANCE_ORDER", "binding"))
        return None
    if {row[1] for row in actual} < _REQUIRED_ROLES:
        issues.append(_issue("TSC010_ROLE_MISSING", "binding"))
        return None
    joins = manifest.get("joins")
    if (
        not isinstance(joins, list)
        or {row.get("kind") for row in joins if isinstance(row, dict)}
        != _REQUIRED_JOINS
    ):
        issues.append(_issue("TSC013_INVENTORY_BINDING_ABSENT", "structural_join"))
        return None
    if not _semantic_identity_matches(identity, cover):
        issues.append(_issue("TSC061_CONSUMPTION_DIGEST_MISMATCH", "semantic_digest"))
        return None
    raw_inventory = content.get("inventory")
    if not isinstance(raw_inventory, list):
        issues.append(_issue("TSC013_INVENTORY_BINDING_ABSENT", "binding"))
        return None
    inventory = {row.get("path"): row for row in raw_inventory if isinstance(row, dict)}
    if len(inventory) != len(raw_inventory):
        issues.append(_issue("TSC014_INVENTORY_BINDING_AMBIGUOUS", "binding"))
        return None
    resolved: list[ResolvedStudentConsumptionV2Resource] = []
    for row in rows:
        if not isinstance(row, dict):
            issues.append(_issue("TSC013_INVENTORY_BINDING_ABSENT", "binding"))
            continue
        role, locator = row.get("role"), row.get("inventory_binding")
        if (
            row.get("classification") != _ROLE_CLASSIFICATIONS.get(role)
            or not isinstance(locator, str)
            or not _v1._safe(locator)
            or locator not in inventory
        ):
            issues.append(
                _issue(
                    "TSC016_INVENTORY_REFERENCE_INVALID",
                    "binding",
                    resource_id=row.get("resource_id"),
                )
            )
            continue
        if "training_payload_binding" in row:
            issues.append(
                _issue(
                    "TSC017_LEGACY_TRAINING_BINDING_FORBIDDEN",
                    "binding",
                    resource_id=row.get("resource_id"),
                )
            )
            continue
        file = root / locator
        if (
            not file.is_file()
            or _v1._digest(file) != inventory[locator].get("sha256")
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
        try:
            semantic = resource_semantic_digest(
                file, row["encoding"], row.get("consumption", {})
            )
        except (OSError, TypeError, ValueError, UnicodeDecodeError):
            issues.append(
                _issue(
                    "TSC060_CONSUMPTION_CANONICALIZATION",
                    "semantic_digest",
                    resource_id=row.get("resource_id"),
                )
            )
            continue
        if semantic != row.get("semantic_digest"):
            issues.append(
                _issue(
                    "TSC015_DERIVED_SEMANTIC_INCONSISTENT",
                    "semantic_digest",
                    resource_id=row.get("resource_id"),
                )
            )
            continue
        resolved.append(
            ResolvedStudentConsumptionV2Resource(
                row["resource_id"],
                role,
                row["instance_id"],
                semantic,
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
    _validate_target_resources(resolved, root, identity, issues)
    if not issues:
        _validate_corridor_and_exemplar_resources(resolved, root, identity, issues)
    if issues:
        return None

    def group(roles: set[str]) -> tuple[ResolvedStudentConsumptionV2Resource, ...]:
        return tuple(item for item in resolved if item.role in roles)

    return StudentConsumptionV2Descriptor(
        "radjax_student_consumption_descriptor_v2",
        CONTRACT_ID,
        PROFILE_ID,
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
        tuple(joins),
        {"transport": _v1._nested(cover, "package", "transport")},
        dict(manifest.get("provenance", {})),
        tuple(warnings),
        ("not_a_student_loader", "not_a_training_policy"),
    )


def resource_semantic_digest(
    path: Path, encoding: str, consumption: dict[str, Any]
) -> str:
    """Return the V2 canonical semantic digest for a derived resource."""

    if encoding == "json":
        payload = _canonical_json_bytes(_strict_json(path.read_text(encoding="utf-8")))
    elif encoding == "jsonl":
        raw = path.read_bytes()
        if not raw or not raw.endswith(b"\n") or b"\r" in raw:
            raise ValueError("canonical JSONL requires LF terminated records")
        payload = b"".join(
            _canonical_json_bytes(_strict_json(line.decode("utf-8"))) + b"\n"
            for line in raw.splitlines()
            if line
        )
        if b"\n\n" in raw:
            raise ValueError("blank JSONL record")
    elif encoding == "npz":
        payload = _canonical_npz_bytes(path, consumption)
    else:
        raise ValueError("unsupported semantic resource encoding")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_npz_bytes(path: Path, consumption: dict[str, Any]) -> bytes:
    axes = consumption.get("axes")
    if not isinstance(axes, dict):
        raise ValueError("axes declaration must be object")
    frames: list[bytes] = []
    with np.load(path, allow_pickle=False) as archive:
        names = list(archive.files)
        if len(names) != len(set(names)):
            raise ValueError("duplicate NPZ member")
        if set(axes) != set(names):
            raise ValueError("axes must declare every NPZ member")
        for name in sorted(names):
            array = archive[name]
            if array.dtype.hasobject:
                raise ValueError("object array")
            canonical = np.ascontiguousarray(
                array.astype(array.dtype.newbyteorder("<"), copy=False)
            )
            declared_axes = axes[name]
            if (
                not isinstance(declared_axes, list)
                or len(declared_axes) != canonical.ndim
            ):
                raise ValueError("invalid axes declaration")
            for part in (
                name.encode("utf-8"),
                canonical.dtype.str.encode("ascii"),
                str(canonical.ndim).encode("ascii"),
                json.dumps(list(canonical.shape), separators=(",", ":")).encode(
                    "ascii"
                ),
                _canonical_json_bytes(declared_axes),
                canonical.tobytes(order="C"),
            ):
                frames.append(struct.pack("<Q", len(part)) + part)
    return b"".join(frames)


def _strict_json(text: str) -> Any:
    if text.startswith("\ufeff"):
        raise ValueError("BOM")
    return json.loads(
        text,
        object_pairs_hook=_v1._unique_object,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
    )


def _canonical_json_bytes(value: Any) -> bytes:
    def reject_negative_zero(item: Any) -> None:
        if isinstance(item, float):
            if not np.isfinite(item) or (item == 0.0 and np.signbit(item)):
                raise ValueError("noncanonical float")
        elif isinstance(item, dict):
            for nested in item.values():
                reject_negative_zero(nested)
        elif isinstance(item, list):
            for nested in item:
                reject_negative_zero(nested)

    reject_negative_zero(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _resource_projection(rows: Any) -> list[tuple[Any, Any, Any, Any]] | None:
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return None
    return [
        (
            row.get("resource_id"),
            row.get("role"),
            row.get("instance_id"),
            row.get("semantic_digest"),
        )
        for row in rows
    ]


def _semantic_identity_matches(identity: dict[str, Any], cover: dict[str, Any]) -> bool:
    digest = identity.get("semantic_digest")
    sidecar = cover.get("student_consumption")
    if not isinstance(digest, str) or not isinstance(sidecar, dict):
        return False
    projection = {
        key: value for key, value in identity.items() if key != "semantic_digest"
    }
    try:
        expected = (
            "sha256:" + hashlib.sha256(_canonical_json_bytes(projection)).hexdigest()
        )
    except (TypeError, ValueError):
        return False
    return digest == expected and sidecar.get("semantic_digest") == expected


def _validate_manifest(manifest: dict[str, Any]) -> bool:
    root = contract_root() / "schemas"
    try:
        identity = json.loads(
            (root / "student_consumption_semantic_identity_v2.json").read_text(
                encoding="utf-8"
            )
        )
        schema = json.loads(
            (root / "student_consumption_manifest_v2.json").read_text(encoding="utf-8")
        )
        registry = Registry().with_resources(
            [(identity["$id"], Resource.from_contents(identity))]
        )
        Draft202012Validator(schema, registry=registry).validate(manifest)
    except (OSError, ValueError, KeyError):
        return False
    except Exception as exc:
        if exc.__class__.__module__.startswith("jsonschema"):
            return False
        raise
    return True


def _validate_cover(cover: dict[str, Any]) -> bool:
    try:
        schema = json.loads(
            (
                contract_root() / "schemas/tome_cover_v3_student_consumption_v2.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(cover)
    except (OSError, ValueError, KeyError):
        return False
    except Exception as exc:
        if exc.__class__.__module__.startswith("jsonschema"):
            return False
        raise
    return True


def _validate_target_resources(
    resources: list[ResolvedStudentConsumptionV2Resource],
    root: Path,
    identity: dict[str, Any],
    issues: list[_v1.StudentConsumptionIssue],
) -> None:
    _v1._validate_target_resources(resources, root, identity, issues)
    _reprofile(issues)


def _validate_corridor_and_exemplar_resources(
    resources: list[ResolvedStudentConsumptionV2Resource],
    root: Path,
    identity: dict[str, Any],
    issues: list[_v1.StudentConsumptionIssue],
) -> None:
    initial = len(issues)
    for finding in validate_corridor_resources(resources, root):
        issues.append(
            _issue(
                finding.code,
                "corridor" if finding.code.startswith("TSC04") else "encoding",
                **finding.context,
            )
        )
    if len(issues) != initial:
        return
    roles = {item.role: item for item in resources}
    try:
        passport = _read_object(
            root / roles["selected_passport_index"].locator, issues, "exemplar"
        )
        exemplar = _read_object(
            root / roles["selected_exemplar_payload"].locator, issues, "exemplar"
        )
        coordinates = _v1._exemplar_corridor_coordinates(
            root, roles["example_registry"], roles["corridor_assignment"], issues
        )
        if coordinates is None or not passport or not exemplar:
            return
        for finding in validate_exemplar_passport_semantics(
            passport["selected_exemplars"],
            exemplar["selected_exemplars"],
            corridor_coordinates=coordinates,
            vocabulary_size=_v1._nested(identity, "vocabulary", "vocab_size"),
        ):
            issues.append(
                _issue(
                    finding.code,
                    "provenance"
                    if finding.code == "TSC055_PROVENANCE_CONTRADICTION"
                    else "exemplar",
                    **finding.context,
                )
            )
    except (KeyError, TypeError, ValueError):
        issues.append(_issue("TSC050_PASSPORT_JOIN_INVALID", "exemplar"))


def _read_object(
    path: Path, issues: list[_v1.StudentConsumptionIssue], phase: str
) -> dict[str, Any] | None:
    try:
        value = _strict_json(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("object")
        return value
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        issues.append(_issue("TSC060_CONSUMPTION_CANONICALIZATION", phase))
        return None


def _issue(code: str, phase: str, **context: Any) -> _v1.StudentConsumptionIssue:
    return _v1.StudentConsumptionIssue(code, phase, PROFILE_ID, context)


def _reprofile(issues: list[_v1.StudentConsumptionIssue]) -> None:
    for index, item in enumerate(issues):
        if item.profile_id != PROFILE_ID:
            issues[index] = _v1.StudentConsumptionIssue(
                item.code, item.phase, PROFILE_ID, item.context
            )


def _result(
    issues: list[_v1.StudentConsumptionIssue],
    warnings: list[_v1.StudentConsumptionIssue],
    descriptor: StudentConsumptionV2Descriptor | None = None,
) -> StudentConsumptionV2ValidationResult:
    order = {phase: index for index, phase in enumerate(_PHASES)}

    def key(item: _v1.StudentConsumptionIssue) -> tuple[int, str, str]:
        return (
            order.get(item.phase, len(order)),
            str(item.context.get("resource_id", item.context.get("locator", ""))),
            item.code,
        )

    ordered, ordered_warnings = (
        tuple(sorted(issues, key=key)),
        tuple(sorted(warnings, key=key)),
    )
    return StudentConsumptionV2ValidationResult(
        not ordered,
        PROFILE_ID,
        ordered,
        ordered_warnings,
        None if ordered else descriptor,
    )
