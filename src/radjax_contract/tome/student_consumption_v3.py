"""Native-v3 Student-consumption v3 admission.

The v3 profile is deliberately an opt-in public boundary.  It retains the
portable, independently-digested resource checks of v2 and additionally binds
the row-range, delivery, and authority evidence sidecars to those resources.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from radjax_contract.tome import student_consumption as _v1
from radjax_contract.tome import student_consumption_v2 as _v2

PROFILE_ID = "native_v3_student_v3"
CONTRACT_ID = "radjax_tome_student_consumption_contract"
_MANIFEST_PATH = "manifests/student_consumption_v3.json"
_IDENTITY_SCHEMA = "radjax_tome_student_consumption_semantic_identity_v3"


def contract_root() -> Path:
    """Return the installed v3 Student-consumption contract assets."""

    root = files("radjax_contract").joinpath(
        "contracts", "radjax_tome", "student_consumption", "v3"
    )
    return Path(str(root))


@dataclass(frozen=True)
class StudentConsumptionV3Descriptor:
    schema_version: str
    contract_id: str
    profile_id: str
    base_artifact_semantic_digest: str
    consumption_semantic_digest: str
    vocabulary: dict[str, Any]
    sequence: dict[str, Any]
    corridor_resources: tuple[_v2.ResolvedStudentConsumptionV2Resource, ...]
    exemplar_resources: tuple[_v2.ResolvedStudentConsumptionV2Resource, ...]
    validation_resources: tuple[_v2.ResolvedStudentConsumptionV2Resource, ...]
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
class StudentConsumptionV3ValidationResult:
    ok: bool
    profile_id: str
    issues: tuple[_v1.StudentConsumptionIssue, ...]
    warnings: tuple[_v1.StudentConsumptionIssue, ...]
    descriptor: StudentConsumptionV3Descriptor | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "radjax_student_consumption_validation_result_v3",
            "ok": self.ok,
            "profile_id": self.profile_id,
            "issues": [item.to_dict() for item in self.issues],
            "warnings": [item.to_dict() for item in self.warnings],
            "descriptor": None
            if self.descriptor is None
            else self.descriptor.to_dict(),
        }


def validate_and_resolve_student_consumption_v3(
    artifact: str | Path, *, strict: bool = False
) -> StudentConsumptionV3ValidationResult:
    """Validate an explicitly negotiated v3 profile; never downgrade it."""

    issues: list[_v1.StudentConsumptionIssue] = []
    warnings: list[_v1.StudentConsumptionIssue] = []
    artifact_path = Path(artifact)
    with _v1._artifact_root(artifact_path, issues, warnings) as root:
        _reprofile(issues)
        _reprofile(warnings)
        if root is None:
            return _result(issues, warnings)
        cover = _read_object(root / "cover_page.json", issues, "profile_cover")
        if cover is None:
            return _result(issues, warnings)
        if cover.get("schema_version") != "radjax_tome_cover_v3_student_consumption_v3":
            issues.append(_issue("TSC002_COVER_VERSION_UNSUPPORTED", "profile_cover"))
            return _result(issues, warnings)
        if not _validate_cover(cover):
            issues.append(_issue("TSC002_COVER_VERSION_UNSUPPORTED", "profile_cover"))
            return _result(issues, warnings)
        if _v1._nested(cover, "package", "transport") != (
            "directory"
            if artifact_path.is_dir()
            else _v1._archive_transport(artifact_path)
        ):
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
        # The profile id is the sole negotiation.  Capabilities are not a
        # permissive fallback channel for an otherwise incompatible profile.
        if (
            sidecar.get("digest_method") != "sha256"
            or sidecar.get("required_capabilities") != []
        ):
            issues.append(_issue("TSC003_REQUIRED_CAPABILITY_UNKNOWN", "profile_cover"))
            return _result(issues, warnings)
        manifest = _verified_manifest(root, sidecar, content, issues)
        if manifest is None or not _validate_manifest(manifest):
            if not issues:
                issues.append(_issue("TSC013_INVENTORY_BINDING_ABSENT", "binding"))
            return _result(issues, warnings)
        if (
            manifest.get("profile_id") != PROFILE_ID
            or manifest.get("schema_version")
            != "radjax_tome_student_consumption_manifest_v3"
        ):
            issues.append(_issue("TSC001_PROFILE_UNSUPPORTED", "profile_cover"))
            return _result(issues, warnings)
        identity = manifest.get("semantic_identity")
        if not isinstance(identity, dict) or not _identity_matches(identity, sidecar):
            issues.append(
                _issue("TSC061_CONSUMPTION_DIGEST_MISMATCH", "semantic_digest")
            )
            return _result(issues, warnings)
        v2_result = _resolve_base_v2(root, cover, manifest)
        if not v2_result.ok or v2_result.descriptor is None:
            issues.extend(_reprofile_copy(v2_result.issues))
            warnings.extend(_reprofile_copy(v2_result.warnings))
            return _result(issues, warnings)
        descriptor = v2_result.descriptor
        _validate_v3_evidence(root, manifest, identity, descriptor, issues)
        warnings.extend(_reprofile_copy(v2_result.warnings))
        if strict and warnings:
            issues.extend(warnings)
            warnings.clear()
        if issues:
            return _result(issues, warnings)
        return _result(
            issues,
            warnings,
            StudentConsumptionV3Descriptor(
                "radjax_student_consumption_descriptor_v3",
                CONTRACT_ID,
                PROFILE_ID,
                descriptor.base_artifact_semantic_digest,
                identity["semantic_digest"],
                descriptor.vocabulary,
                descriptor.sequence,
                descriptor.corridor_resources,
                descriptor.exemplar_resources,
                descriptor.validation_resources,
                descriptor.joins,
                descriptor.delivery,
                descriptor.provenance,
                tuple(warnings),
                (
                    "not_a_student_loader",
                    "not_a_training_policy",
                    "not_a_full_artifact_copy",
                ),
            ),
        )


@contextmanager
def open_verified_student_resource_v3(
    artifact: str | Path, resource_id: str, *, strict: bool = False
):
    """Open one v3-admitted resource while rechecking its raw integrity."""

    result = validate_and_resolve_student_consumption_v3(artifact, strict=strict)
    if not result.ok or result.descriptor is None:
        raise ValueError(
            "Student-consumption validation failed: "
            + ",".join(x.code for x in result.issues)
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


def _verified_manifest(
    root: Path,
    sidecar: dict[str, Any],
    content: dict[str, Any],
    issues: list[_v1.StudentConsumptionIssue],
) -> dict[str, Any] | None:
    path = sidecar.get("manifest_path")
    inventory = content.get("inventory")
    if path != _MANIFEST_PATH or not isinstance(inventory, list):
        issues.append(
            _issue("TSC016_INVENTORY_REFERENCE_INVALID", "inventory_integrity")
        )
        return None
    matches = [
        row for row in inventory if isinstance(row, dict) and row.get("path") == path
    ]
    if len(matches) != 1 or not _v1._safe(path):
        issues.append(
            _issue("TSC014_INVENTORY_BINDING_AMBIGUOUS", "binding", manifest_path=path)
        )
        return None
    file = root / path
    if not file.is_file():
        issues.append(
            _issue("TSC022_RESOURCE_UNAVAILABLE", "inventory_integrity", locator=path)
        )
        return None
    digest = _v1._digest(file)
    if digest != matches[0].get("sha256") or digest != sidecar.get("manifest_sha256"):
        issues.append(
            _issue(
                "TSC023_RESOURCE_INTEGRITY_MISMATCH",
                "inventory_integrity",
                locator=path,
            )
        )
        return None
    return _read_object(file, issues, "binding")


def _resolve_base_v2(
    root: Path, cover: dict[str, Any], manifest: dict[str, Any]
) -> _v2.StudentConsumptionV2ValidationResult:
    """Use v2's resource semantics after a lossless in-memory profile rewrite."""

    with tempfile.TemporaryDirectory(prefix="radjax-tsc-v3-") as tmp:
        stage = Path(tmp) / "artifact"
        shutil.copytree(root, stage)
        normalized = json.loads(json.dumps(manifest))
        identity = normalized["semantic_identity"]
        identity["schema_version"] = (
            "radjax_tome_student_consumption_semantic_identity_v2"
        )
        identity["profile_id"] = "native_v3_student_v2"
        # V2 is used solely for its portable resource mechanics; its identity
        # schema intentionally has no v3 score-authority extension.
        identity["authority"] = {
            "selection_integration_config_hash": identity["authority"][
                "selection_integration_config_hash"
            ]
        }
        for row in normalized["resources"]:
            if row["role"] in {
                "row_range_declaration",
                "delivery_receipt",
                "authority_reference",
            }:
                row["consumption"] = {"kind": row["role"]}
        identity["semantic_digest"] = _identity_digest(identity)
        normalized["schema_version"] = "radjax_tome_student_consumption_manifest_v2"
        normalized["profile_id"] = "native_v3_student_v2"
        v2_path = stage / "manifests/student_consumption_v2.json"
        v2_path.write_text(json.dumps(normalized, sort_keys=True), encoding="utf-8")
        stage_cover = json.loads(json.dumps(cover))
        sidecar = stage_cover["student_consumption"]
        sidecar.update(
            {
                "profile_id": "native_v3_student_v2",
                "manifest_path": "manifests/student_consumption_v2.json",
                "manifest_sha256": _v1._digest(v2_path),
                "semantic_digest": identity["semantic_digest"],
            }
        )
        stage_cover["schema_version"] = "radjax_tome_cover_v3_student_consumption_v2"
        inventory = stage_cover["manifests"]["content"]["inventory"]
        inventory[:] = [
            row
            for row in inventory
            if row.get("path")
            not in {_MANIFEST_PATH, "manifests/student_consumption_v2.json"}
        ]
        inventory.append(
            {
                "path": "manifests/student_consumption_v2.json",
                "sha256": _v1._digest(v2_path),
                "size_bytes": v2_path.stat().st_size,
                "classification": "manifest",
                "training_authoritative": False,
            }
        )
        (stage / "cover_page.json").write_text(
            json.dumps(stage_cover, sort_keys=True), encoding="utf-8"
        )
        return _v2.validate_and_resolve_student_consumption_v2(stage)


def _validate_v3_evidence(
    root: Path,
    manifest: dict[str, Any],
    identity: dict[str, Any],
    descriptor: _v2.StudentConsumptionV2Descriptor,
    issues: list[_v1.StudentConsumptionIssue],
) -> None:
    rows = {item.role: item for item in descriptor.validation_resources}
    ranges = _body(root, rows.get("row_range_declaration"), issues, "structural_join")
    receipt = _body(root, rows.get("delivery_receipt"), issues, "provenance")
    authority = _body(root, rows.get("authority_reference"), issues, "provenance")
    if ranges is not None:
        expected_examples = sum(
            item.consumption["row_end"] - item.consumption["row_start"]
            for item in descriptor.corridor_resources
            if item.role == "target_shard"
        )
        assignment = next(
            (
                item
                for item in descriptor.corridor_resources
                if item.role == "corridor_assignment"
            ),
            None,
        )
        try:
            with np.load(root / assignment.locator, allow_pickle=False) as payload:
                expected_assignments = len(payload["position"])
        except (AttributeError, KeyError, OSError, ValueError):
            expected_assignments = -1
        exact = {"schema_version", "example_count", "assignment_count", "ordering"}
        if (
            set(ranges) != exact
            or ranges.get("schema_version")
            != "native_v3_student_consumption_row_ranges_v1"
            or ranges.get("ordering") != "example_index_then_source_position"
            or any(
                isinstance(ranges.get(key), bool)
                or not isinstance(ranges.get(key), int)
                or ranges[key] <= 0
                for key in ("example_count", "assignment_count")
            )
            or ranges.get("example_count") != expected_examples
            or ranges.get("assignment_count") != expected_assignments
        ):
            issues.append(
                _issue("TSC070_ROW_RANGE_DECLARATION_INVALID", "structural_join")
            )
    if receipt is not None:
        exact = {
            "schema_version",
            "delivery_path",
            "assignment_encoding",
            "statistics_encoding",
            "source_roles",
        }
        valid = (
            set(receipt) == exact
            and receipt.get("schema_version")
            == "native_v3_student_consumption_delivery_receipt_v2"
            and receipt.get("assignment_encoding") == "npz_named_arrays_v1"
            and receipt.get("statistics_encoding") == "npz_named_arrays_v1"
            and receipt.get("delivery_path")
            in {"one_pass_full", "two_pass_rerun_selected"}
            and receipt.get("source_roles")
            == ["native_v3_mode_assignments", "native_v3_score_shards"]
        )
        if not valid:
            issues.append(_issue("TSC071_DELIVERY_RECEIPT_INVALID", "provenance"))
    if authority is not None:
        allowed = {
            "schema_version",
            "selection_integration_config_hash",
            "score_pass_authority_hash",
            "score_pass_authority_hash_v1",
            "delivery_authority_hash",
        }
        scores = [
            authority.get(key)
            for key in ("score_pass_authority_hash", "score_pass_authority_hash_v1")
            if key in authority
        ]
        hashes = scores + [
            authority[key] for key in ("delivery_authority_hash",) if key in authority
        ]
        valid = (
            set(authority) <= allowed
            and authority.get("schema_version")
            == "native_v3_student_consumption_authority_reference_v1"
            and bool(scores)
            and all(_sha256_syntax(value) for value in hashes)
            and authority.get("selection_integration_config_hash")
            == _v1._nested(identity, "authority", "selection_integration_config_hash")
        )
        if not valid:
            issues.append(_issue("TSC072_AUTHORITY_REFERENCE_MISMATCH", "provenance"))


def _body(
    root: Path, resource: Any, issues: list[_v1.StudentConsumptionIssue], phase: str
) -> dict[str, Any] | None:
    if resource is None or resource.encoding != "json":
        issues.append(_issue("TSC060_CONSUMPTION_CANONICALIZATION", phase))
        return None
    return _read_object(root / resource.locator, issues, phase)


def _identity_digest(identity: dict[str, Any]) -> str:
    projection = {
        key: value for key, value in identity.items() if key != "semantic_digest"
    }
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()
    )


def _sha256_syntax(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _identity_matches(identity: dict[str, Any], sidecar: dict[str, Any]) -> bool:
    return (
        identity.get("schema_version") == _IDENTITY_SCHEMA
        and identity.get("profile_id") == PROFILE_ID
        and isinstance(identity.get("semantic_digest"), str)
        and identity.get("semantic_digest") == _identity_digest(identity)
        and sidecar.get("semantic_digest") == identity.get("semantic_digest")
    )


def _validate_manifest(manifest: dict[str, Any]) -> bool:
    return _validate_schema(
        manifest,
        "student_consumption_manifest_v3.json",
        "student_consumption_semantic_identity_v3.json",
    )


def _validate_cover(cover: dict[str, Any]) -> bool:
    return _validate_schema(cover, "tome_cover_v3_student_consumption_v3.json")


def _validate_schema(
    value: dict[str, Any], schema_name: str, identity_name: str | None = None
) -> bool:
    try:
        schemas = contract_root() / "schemas"
        schema = json.loads((schemas / schema_name).read_text(encoding="utf-8"))
        if identity_name is None:
            Draft202012Validator(schema).validate(value)
        else:
            identity = json.loads((schemas / identity_name).read_text(encoding="utf-8"))
            registry = Registry().with_resources(
                [(identity["$id"], Resource.from_contents(identity))]
            )
            Draft202012Validator(schema, registry=registry).validate(value)
    except (OSError, ValueError, KeyError):
        return False
    except Exception as exc:
        if exc.__class__.__module__.startswith("jsonschema"):
            return False
        raise
    return True


def _read_object(
    path: Path, issues: list[_v1.StudentConsumptionIssue], phase: str
) -> dict[str, Any] | None:
    try:
        value = _v2._strict_json(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("object required")
        return value
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        issues.append(_issue("TSC060_CONSUMPTION_CANONICALIZATION", phase))
        return None


def _issue(code: str, phase: str, **context: Any) -> _v1.StudentConsumptionIssue:
    return _v1.StudentConsumptionIssue(code, phase, PROFILE_ID, context)


def _reprofile(items: list[_v1.StudentConsumptionIssue]) -> None:
    items[:] = _reprofile_copy(items)


def _reprofile_copy(
    items: tuple[_v1.StudentConsumptionIssue, ...] | list[_v1.StudentConsumptionIssue],
) -> list[_v1.StudentConsumptionIssue]:
    return [
        _v1.StudentConsumptionIssue(item.code, item.phase, PROFILE_ID, item.context)
        for item in items
    ]


def _result(
    issues: list[_v1.StudentConsumptionIssue],
    warnings: list[_v1.StudentConsumptionIssue],
    descriptor: StudentConsumptionV3Descriptor | None = None,
) -> StudentConsumptionV3ValidationResult:
    order = {phase: index for index, phase in enumerate(_v1._PHASES)}

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
    return StudentConsumptionV3ValidationResult(
        not ordered,
        PROFILE_ID,
        ordered,
        ordered_warnings,
        descriptor if not ordered else None,
    )
