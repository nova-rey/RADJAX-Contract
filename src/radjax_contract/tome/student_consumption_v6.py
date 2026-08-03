"""Additive behavioral-resource authority for ``native_v3_student_v6``.

V6 deliberately composes the immutable V5 language/tokenizer binding with a
closed, architecture-neutral behavioral registry.  This module owns canonical
logical identities; physical package admission and verified opening are added
below these primitives so a delivery locator can never influence behavioral
replay equivalence.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator, ValidationError

from radjax_contract.tome import student_consumption as _v1
from radjax_contract.tome.contract_publication import (
    tome_student_consumption_v6_contract_asset_path,
)
from radjax_contract.tome.language_tokenizer_binding_v1 import (
    LanguageTokenizerBindingDescriptor,
    canonical_json_bytes,
    validate_and_resolve_language_tokenizer_binding,
)
from radjax_contract.tome.streaming_validation import (
    ContractError as M7ContractError,
)
from radjax_contract.tome.streaming_validation import (
    StreamingTomeReader,
    open_streaming_tome,
)
from radjax_contract.tome.student_exemplar_semantics import (
    validate_exemplar_passport_semantics,
)

PROFILE_ID = "native_v3_student_v6"
CONTRACT_ID = "radjax_tome_student_consumption_contract"
BEHAVIORAL_SCHEMA_VERSION = "radjax_behavioral_resource_binding_v1"

AUTHORITY_ROLES = (
    "target_shard",
    "example_registry",
    "corridor_mode_table",
    "corridor_assignment",
    "selected_passport_index",
    "selected_exemplar_payload",
    "authority_reference",
)
NON_AUTHORITY_ROLES = ("delivery_receipt",)
REQUIRED_ROLES = frozenset((*AUTHORITY_ROLES, *NON_AUTHORITY_ROLES))
_MANIFEST_PATH = "manifests/behavioral_resource_binding_v1.json"
_PHASES = (
    "profile",
    "archive_safety",
    "integrity",
    "binding",
    "encoding",
    "structural_join",
    "corridor",
    "exemplar",
    "provenance",
    "identity",
)


@dataclass(frozen=True)
class BehavioralResourceIssue:
    """A deterministic v6 rejection with a stable phase and code."""

    code: str
    phase: str
    profile_id: str
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedBehavioralResource:
    """A declared logical resource and its physical integrity binding."""

    resource_id: str
    role: str
    schema: str
    encoding: str
    semantic_identity: str
    raw_sha256: str
    raw_size_bytes: int
    locator: str
    authority: bool
    components: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BehavioralAuthorityDescriptor:
    """Resolved v6 identities with replay and exact-package domains separate."""

    schema_version: str
    contract_id: str
    profile_id: str
    language_binding_digest: str
    behavioral_source_identity: str
    behavioral_authority_digest: str
    package_semantic_identity: str
    composition_digest: str
    authority_resources: tuple[ResolvedBehavioralResource, ...]
    non_authority_resources: tuple[ResolvedBehavioralResource, ...]
    required_joins: tuple[str, ...]
    nonclaims: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["authority_resources"] = [
            item.to_dict() for item in self.authority_resources
        ]
        result["non_authority_resources"] = [
            item.to_dict() for item in self.non_authority_resources
        ]
        result["required_joins"] = list(self.required_joins)
        result["nonclaims"] = list(self.nonclaims)
        return result


@dataclass(frozen=True)
class BehavioralAuthorityValidationResult:
    """Result of exact-profile v6 admission; no legacy fallback is attempted."""

    ok: bool
    profile_id: str
    issues: tuple[BehavioralResourceIssue, ...]
    warnings: tuple[BehavioralResourceIssue, ...]
    descriptor: BehavioralAuthorityDescriptor | None
    _language_binding: LanguageTokenizerBindingDescriptor | None = field(
        default=None, repr=False, compare=False
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "radjax_behavioral_resource_validation_result_v1",
            "ok": self.ok,
            "profile_id": self.profile_id,
            "issues": [item.to_dict() for item in self.issues],
            "warnings": [item.to_dict() for item in self.warnings],
            "descriptor": None
            if self.descriptor is None
            else self.descriptor.to_dict(),
        }


def resolve_student_language_binding(
    artifact: str | Path,
    *,
    profile_id: str = PROFILE_ID,
    strict: bool = True,
) -> LanguageTokenizerBindingDescriptor:
    """Return the v5 language binding subordinate to one strict v6 admission."""

    if profile_id != PROFILE_ID:
        raise ValueError(f"unsupported language projection profile: {profile_id}")
    if not strict:
        raise ValueError("v6 language projection requires strict admission")
    result = validate_and_resolve_student_consumption_v6(artifact, strict=True)
    if not result.ok or result.descriptor is None or result._language_binding is None:
        raise ValueError(
            "v6 language projection admission failed: "
            + ",".join(item.code for item in result.issues)
        )
    language = result._language_binding
    if language.canonical_binding_digest != result.descriptor.language_binding_digest:
        raise ValueError("v6 language projection digest mismatch")
    return language


def sha256_identity(payload: bytes) -> str:
    """Return the one allowed textual representation of a SHA-256 identity."""

    return "sha256:" + hashlib.sha256(payload).hexdigest()


def canonical_npy_component_identity(
    *,
    role: str,
    component: str,
    array: np.ndarray,
    axes: tuple[str, ...],
) -> str:
    """Hash a logical NPY component, not its file/container serialization.

    The explicit frame makes dtype, rank, shape and declared axis names part
    of the identity.  Values are C-order bytes in the declared dtype; object
    arrays are categorically excluded so no pickle or host representation can
    become authority.
    """

    if not role or not component or array.dtype.hasobject:
        raise ValueError("NPY authority component must be named and non-object")
    if (
        array.ndim != len(axes)
        or len(set(axes)) != len(axes)
        or any(not axis for axis in axes)
    ):
        raise ValueError("NPY authority axes must name every dimension exactly once")
    normalized = np.ascontiguousarray(array)
    header = canonical_json_bytes(
        {
            "frame": "radjax_npy_authority_component_v1",
            "role": role,
            "component": component,
            "dtype": normalized.dtype.str,
            "rank": normalized.ndim,
            "shape": list(normalized.shape),
            "axes": list(axes),
        }
    )
    return sha256_identity(
        len(header).to_bytes(8, "big") + header + normalized.tobytes(order="C")
    )


def canonical_multipart_npy_identity(
    *, role: str, components: list[dict[str, Any]]
) -> str:
    """Return an ordered logical identity for independently stored NPY members."""

    names = [component.get("component") for component in components]
    if (
        not role
        or not components
        or any(not isinstance(name, str) or not name for name in names)
        or len(set(names)) != len(names)
        or names != sorted(names)
    ):
        raise ValueError("multipart NPY components must be nonempty and name-sorted")
    projection = {
        "frame": "radjax_npy_authority_multipart_v1",
        "role": role,
        "components": [
            {
                "component": component["component"],
                "semantic_identity": component["semantic_identity"],
            }
            for component in components
        ],
    }
    return sha256_identity(canonical_json_bytes(projection))


def canonical_record_sequence_identity(
    *, role: str, records: list[dict[str, Any]]
) -> str:
    """Hash canonical JSONL logical records with explicit record framing."""

    digest = hashlib.sha256()
    digest.update(b"radjax_record_sequence_v1\0")
    digest.update(role.encode("utf-8"))
    digest.update(b"\0")
    for record in records:
        encoded = canonical_json_bytes(record)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return "sha256:" + digest.hexdigest()


def canonical_selected_passport_identity(records: list[dict[str, Any]]) -> str:
    """Hash exactly the approved v6 passport projection, never raw rows."""

    fields = (
        "schema_version",
        "selected_example_id",
        "selected_position",
        "rank",
        "selected_score",
        "selected_policy",
        "corridor_mode_id",
        "corridor_fingerprint_id",
        "corridor_assignment_status",
        "selection_integration_config_hash",
    )
    projected = []
    for rank, row in enumerate(records, start=1):
        if (
            set(row) != set(fields)
            or row.get("schema_version") != "radjax_selected_passport_v6"
            or row.get("rank") != rank
            or row.get("corridor_assignment_status") != "selected"
            or not isinstance(row.get("selected_example_id"), str)
            or not row["selected_example_id"]
            or type(row.get("selected_position")) is not int
            or row["selected_position"] < 0
            or not _finite(row.get("selected_score"))
            or not isinstance(row.get("selected_policy"), str)
            or not row["selected_policy"]
            or type(row.get("corridor_mode_id")) is not int
            or row["corridor_mode_id"] < 0
            or not isinstance(row.get("corridor_fingerprint_id"), str)
            or not row["corridor_fingerprint_id"]
            or not _identity_syntax(row.get("selection_integration_config_hash"))
        ):
            raise ValueError("selected passport fields are closed")
        projected.append({field: row[field] for field in fields})
    return canonical_record_sequence_identity(
        role="selected_passport_index", records=projected
    )


def canonical_authority_reference_identity(reference: dict[str, Any]) -> str:
    """Hash the approved closed score/selection/delivery authority fields."""

    fields = (
        "schema_version",
        "selection_integration_config_hash",
        "score_pass_authority_hash",
        "delivery_authority_hash",
    )
    if (
        set(reference) != set(fields)
        or reference.get("schema_version") != "radjax_behavioral_authority_reference_v6"
        or any(not _identity_syntax(reference[field]) for field in fields[1:])
    ):
        raise ValueError("authority reference projection is invalid")
    return sha256_identity(canonical_json_bytes(reference))


def canonical_behavioral_source_identity(
    *,
    language_binding_digest: str,
    target_semantic_identity: str,
    example_registry_semantic_identity: str,
    target_shape: tuple[int, int],
    target_axes: tuple[str, str],
) -> str:
    """Bind V5 language authority to v6 target and stable row identity."""

    _require_identity(language_binding_digest)
    _require_identity(target_semantic_identity)
    _require_identity(example_registry_semantic_identity)
    if len(target_shape) != 2 or any(value <= 0 for value in target_shape):
        raise ValueError("target shape must be a positive rank-two grid")
    if target_axes != ("example", "sequence_position"):
        raise ValueError("target axes must be example and sequence_position")
    return sha256_identity(
        canonical_json_bytes(
            {
                "schema_version": "radjax_behavioral_source_identity_v1",
                "language_binding_digest": language_binding_digest,
                "target_semantic_identity": target_semantic_identity,
                "example_registry_semantic_identity": (
                    example_registry_semantic_identity
                ),
                "target_shape": list(target_shape),
                "target_axes": list(target_axes),
            }
        )
    )


def canonical_behavioral_authority_digest(
    *,
    language_binding_digest: str,
    behavioral_source_identity: str,
    authority_registry: list[dict[str, str]],
    required_joins: tuple[str, ...],
    selection_authority_digest: str,
) -> str:
    """Digest behavioral replay authority, intentionally excluding delivery."""

    _require_identity(language_binding_digest)
    _require_identity(behavioral_source_identity)
    _require_identity(selection_authority_digest)
    _validate_registry(authority_registry, expected_authority=True)
    if not required_joins or len(set(required_joins)) != len(required_joins):
        raise ValueError("required joins must be a unique nonempty ordered tuple")
    return sha256_identity(
        canonical_json_bytes(
            {
                "schema_version": "radjax_behavioral_authority_digest_v1",
                "profile_id": PROFILE_ID,
                "language_binding_digest": language_binding_digest,
                "behavioral_source_identity": behavioral_source_identity,
                "authority_registry": authority_registry,
                "required_joins": list(required_joins),
                "selection_authority_digest": selection_authority_digest,
            }
        )
    )


def canonical_composition_digest(
    *,
    behavioral_authority_digest: str,
    authority_registry: list[dict[str, str]],
    non_authority_registry: list[dict[str, str]],
    package_semantic_identity: str,
) -> str:
    """Bind exact package provenance without redefining behavioral equivalence."""

    _require_identity(behavioral_authority_digest)
    _require_identity(package_semantic_identity)
    _validate_registry(authority_registry, expected_authority=True)
    _validate_registry(non_authority_registry, expected_authority=False)
    return sha256_identity(
        canonical_json_bytes(
            {
                "schema_version": "radjax_behavioral_composition_digest_v1",
                "behavioral_authority_digest": behavioral_authority_digest,
                "authority_registry": authority_registry,
                "non_authority_registry": non_authority_registry,
                "package_semantic_identity": package_semantic_identity,
            }
        )
    )


def _validate_registry(rows: list[dict[str, str]], *, expected_authority: bool) -> None:
    if not rows:
        raise ValueError("registry projection must not be empty")
    previous: tuple[str, str] | None = None
    seen: set[str] = set()
    for row in rows:
        if set(row) != {"resource_id", "role", "schema", "semantic_identity"}:
            raise ValueError("registry projection fields are closed")
        resource_id, role = row["resource_id"], row["role"]
        if not resource_id or resource_id in seen:
            raise ValueError("registry resource IDs must be unique")
        if (role in AUTHORITY_ROLES) != expected_authority:
            raise ValueError("registry role belongs to the wrong authority domain")
        _require_identity(row["semantic_identity"])
        key = (role, resource_id)
        if previous is not None and key <= previous:
            raise ValueError(
                "registry projection must be sorted by role and resource ID"
            )
        previous, seen = key, seen | {resource_id}


def _require_identity(value: Any) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise ValueError("expected lowercase sha256 identity")


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def validate_and_resolve_student_consumption_v6(
    artifact: str | Path, *, strict: bool = False
) -> BehavioralAuthorityValidationResult:
    """Admit one explicit v6 composition without interpreting older packages."""

    issues: list[BehavioralResourceIssue] = []
    warnings: list[BehavioralResourceIssue] = []
    artifact_path = Path(artifact)
    with _v1._artifact_root(artifact_path, [], []) as root:
        if root is None:
            issues.append(_issue("BRC001_ARTIFACT_UNAVAILABLE", "archive_safety"))
            return _result(issues, warnings)
        language = validate_and_resolve_language_tokenizer_binding(root, strict=strict)
        if not language.ok or language.descriptor is None:
            issues.append(
                _issue(
                    "BRC002_LANGUAGE_BINDING_INVALID",
                    "binding",
                    nested_issues=[item.code for item in language.issues],
                )
            )
            return _result(issues, warnings)
        manifest_path = root / _MANIFEST_PATH
        manifest = _read_json(manifest_path, issues, "binding")
        if manifest is None:
            return _result(issues, warnings)
        if (
            manifest.get("schema_version") != BEHAVIORAL_SCHEMA_VERSION
            or manifest.get("profile_id") != PROFILE_ID
        ):
            issues.append(_issue("BRC003_PROFILE_OR_SCHEMA_UNSUPPORTED", "profile"))
            return _result(issues, warnings)
        if not _manifest_schema_valid(manifest):
            issues.append(_issue("BRC004_RESOURCE_REGISTRY_INVALID", "binding"))
            return _result(issues, warnings)
        rows = manifest.get("resources")
        if not isinstance(rows, list):
            issues.append(_issue("BRC004_RESOURCE_REGISTRY_INVALID", "binding"))
            return _result(issues, warnings)
        resources = _resolve_resources(root, rows, issues)
        if issues:
            return _result(issues, warnings)
        by_role = {item.role: item for item in resources}
        target = _validate_target(root, by_role.get("target_shard"), issues)
        examples = _read_jsonl(root, by_role.get("example_registry"), issues)
        mode_ids = _validate_mode_table(
            root, by_role.get("corridor_mode_table"), issues
        )
        assignment = _validate_assignment(
            root, by_role.get("corridor_assignment"), target, mode_ids, issues
        )
        passports = _read_jsonl(root, by_role.get("selected_passport_index"), issues)
        exemplar_resource = by_role.get("selected_exemplar_payload")
        if exemplar_resource is not None and exemplar_resource.encoding == "jsonl":
            exemplars = _read_jsonl(root, exemplar_resource, issues)
            _validate_selected_coordinates(
                target,
                examples,
                assignment,
                passports,
                exemplars,
                language.descriptor.vocabulary["vocabulary_size"],
                issues,
            )
        elif (
            exemplar_resource is not None
            and exemplar_resource.encoding == "m7_tome_archive"
        ):
            _validate_m7_selected_exemplars(
                root,
                exemplar_resource,
                target,
                examples,
                assignment,
                passports,
                language.descriptor.vocabulary["vocabulary_size"],
                issues,
            )
        else:
            issues.append(_issue("BRC013_ENCODING_INVALID", "encoding"))
        _validate_delivery_receipt(root, by_role.get("delivery_receipt"), issues)
        if target is None or examples is None or assignment is None or issues:
            return _result(issues, warnings)
        authority = [item for item in resources if item.authority]
        non_authority = [item for item in resources if not item.authority]
        authority_registry = _registry(authority)
        non_authority_registry = _registry(non_authority)
        source = canonical_behavioral_source_identity(
            language_binding_digest=language.descriptor.canonical_binding_digest,
            target_semantic_identity=by_role["target_shard"].semantic_identity,
            example_registry_semantic_identity=by_role[
                "example_registry"
            ].semantic_identity,
            target_shape=target[0].shape,
            target_axes=("example", "sequence_position"),
        )
        selection = by_role["authority_reference"].semantic_identity
        joins = (
            "assignment_to_target_grid",
            "selected_passport_to_target",
            "selected_exemplar_to_passport",
        )
        behavioral = canonical_behavioral_authority_digest(
            language_binding_digest=language.descriptor.canonical_binding_digest,
            behavioral_source_identity=source,
            authority_registry=authority_registry,
            required_joins=joins,
            selection_authority_digest=selection,
        )
        package_identity = manifest.get("package_semantic_identity")
        if not _identity_syntax(package_identity):
            issues.append(_issue("BRC005_PACKAGE_IDENTITY_INVALID", "identity"))
            return _result(issues, warnings)
        composition = canonical_composition_digest(
            behavioral_authority_digest=behavioral,
            authority_registry=authority_registry,
            non_authority_registry=non_authority_registry,
            package_semantic_identity=package_identity,
        )
        if manifest.get("behavioral_authority_digest") != behavioral:
            issues.append(_issue("BRC006_AUTHORITY_DIGEST_MISMATCH", "identity"))
        if manifest.get("composition_digest") != composition:
            issues.append(_issue("BRC007_COMPOSITION_DIGEST_MISMATCH", "identity"))
        if issues:
            return _result(issues, warnings)
        return _result(
            issues,
            warnings,
            BehavioralAuthorityDescriptor(
                "radjax_behavioral_resource_descriptor_v1",
                CONTRACT_ID,
                PROFILE_ID,
                language.descriptor.canonical_binding_digest,
                source,
                behavioral,
                package_identity,
                composition,
                tuple(authority),
                tuple(non_authority),
                joins,
                (
                    "not_a_student_loader",
                    "not_a_training_policy",
                    "not_an_architecture_descriptor",
                ),
            ),
            language.descriptor,
        )


@contextmanager
def open_verified_student_resource_v6(
    artifact: str | Path, resource_id: str, *, strict: bool = False
):
    """Open immutable verified bytes for one admitted v6 resource.

    This is deliberately a *byte* opener.  In particular, callers must not
    infer record-before-yield semantics from it for a JSONL role; use
    :func:`open_verified_student_jsonl_records_v6` for that contract.
    """

    result = validate_and_resolve_student_consumption_v6(artifact, strict=strict)
    if not result.ok or result.descriptor is None:
        raise ValueError(
            "v6 behavioral-resource validation failed: "
            + ",".join(item.code for item in result.issues)
        )
    resource = _find_resource(result.descriptor, resource_id)
    if resource is None:
        raise ValueError(f"unknown v6 behavioral resource: {resource_id}")
    if resource.encoding == "m7_tome_archive":
        raise ValueError("v6 M7 resources require open_verified_student_m7_payload_v6")
    with _v1._artifact_root(Path(artifact), [], []) as root:
        if root is None:
            raise ValueError("v6 behavioral resource transport is unavailable")
        yield io.BytesIO(_verified_resource_bytes(root, resource))


@contextmanager
def open_verified_student_jsonl_records_v6(
    artifact: str | Path, resource_id: str, *, strict: bool = False
) -> Iterator[Iterator[dict[str, Any]]]:
    """Yield ordinary JSONL records only after whole-resource verification.

    V6 ordinary JSONL resources carry a raw identity for the complete member,
    not a cryptographic identity per row.  This opener therefore reads and
    verifies every byte before parsing or yielding the first record.  The
    returned iterator is over an immutable in-memory tuple, so a post-open
    replacement cannot change a record after the trust transition.

    M7 JSONL is intentionally rejected here: it has a distinct bounded
    shard/index protocol and must use its dedicated opener rather than being
    silently treated as ordinary whole-resource JSONL.
    """

    result = validate_and_resolve_student_consumption_v6(artifact, strict=strict)
    if not result.ok or result.descriptor is None:
        raise ValueError(
            "v6 behavioral-resource validation failed: "
            + ",".join(item.code for item in result.issues)
        )
    resource = _find_resource(result.descriptor, resource_id)
    if resource is None:
        raise ValueError(f"unknown v6 behavioral resource: {resource_id}")
    if resource.encoding != "jsonl":
        raise ValueError("v6 whole-resource JSONL opener requires encoding=jsonl")
    with _v1._artifact_root(Path(artifact), [], []) as root:
        if root is None:
            raise ValueError("v6 behavioral resource transport is unavailable")
        try:
            payload = _verified_resource_bytes(root, resource)
            records = tuple(_parse_jsonl_bytes(payload))
        except ValueError as exc:
            raise ValueError("v6 verified JSONL is invalid at open") from exc
        yield iter(records)


@contextmanager
def open_verified_student_m7_payload_v6(
    artifact: str | Path, resource_id: str, *, strict: bool = False
) -> Iterator[StreamingTomeReader]:
    """Open a v6 M7 payload as a bounded, shard-verified record stream.

    The v6 manifest's outer admission verifies the M7 resource before this
    function is entered.  Opening then creates a fresh sequential M7 reader;
    it verifies the cover/header/index prelude and each shard before records
    from that shard are yielded.  Its ``verification_state`` remains
    ``"closed_early"`` if the caller closes before exhaustion and becomes
    ``"fully_verified"`` only after all shard records have been consumed.
    """

    result = validate_and_resolve_student_consumption_v6(artifact, strict=strict)
    if not result.ok or result.descriptor is None:
        raise ValueError(
            "v6 behavioral-resource validation failed: "
            + ",".join(item.code for item in result.issues)
        )
    resource = _find_resource(result.descriptor, resource_id)
    if resource is None:
        raise ValueError(f"unknown v6 behavioral resource: {resource_id}")
    if resource.encoding != "m7_tome_archive":
        raise ValueError("v6 M7 opener requires encoding=m7_tome_archive")
    with _v1._artifact_root(Path(artifact), [], []) as root:
        if root is None:
            raise ValueError("v6 behavioral resource transport is unavailable")
        try:
            with _staged_verified_m7_archive(root, resource) as archive:
                reader = open_streaming_tome(archive, strict=strict)
                try:
                    yield reader
                finally:
                    reader.close()
        except M7ContractError as exc:
            raise ValueError("v6 M7 resource verification failed at open") from exc


def _resolve_resources(
    root: Path, rows: list[Any], issues: list[BehavioralResourceIssue]
) -> list[ResolvedBehavioralResource]:
    """Resolve the closed one-instance registry and verify raw members first."""

    result: list[ResolvedBehavioralResource] = []
    seen_roles: set[str] = set()
    seen_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            issues.append(_issue("BRC004_RESOURCE_REGISTRY_INVALID", "binding"))
            continue
        role, resource_id = row.get("role"), row.get("resource_id")
        if (
            role not in REQUIRED_ROLES
            or not isinstance(resource_id, str)
            or not resource_id.endswith("/default")
            or role in seen_roles
            or resource_id in seen_ids
        ):
            issues.append(_issue("BRC004_RESOURCE_REGISTRY_INVALID", "binding"))
            continue
        locator = row.get("locator")
        if not isinstance(locator, str) or not _v1._safe(locator):
            issues.append(_issue("BRC008_RESOURCE_LOCATOR_INVALID", "integrity"))
            continue
        raw_sha256, raw_size = row.get("raw_sha256"), row.get("raw_size_bytes")
        if (
            not _identity_syntax(raw_sha256)
            or type(raw_size) is not int
            or raw_size < 0
        ):
            issues.append(_issue("BRC009_RAW_IDENTITY_INVALID", "integrity"))
            continue
        path = root / locator
        if not _raw_matches(path, raw_sha256, raw_size):
            issues.append(
                _issue("BRC010_RAW_INTEGRITY_MISMATCH", "integrity", locator=locator)
            )
            continue
        if row.get("encoding") == "multipart_npy" and not _components_match(
            root, row.get("components")
        ):
            issues.append(
                _issue("BRC010_RAW_INTEGRITY_MISMATCH", "integrity", locator=locator)
            )
            continue
        semantic = _resource_semantic_identity(root, row, issues)
        if semantic is None:
            continue
        if semantic != row.get("semantic_identity"):
            issues.append(
                _issue(
                    "BRC011_RESOURCE_SEMANTIC_MISMATCH",
                    "identity",
                    resource_id=resource_id,
                )
            )
            continue
        result.append(
            ResolvedBehavioralResource(
                resource_id,
                role,
                row.get("schema", ""),
                row.get("encoding", ""),
                semantic,
                raw_sha256,
                raw_size,
                locator,
                role in AUTHORITY_ROLES,
                tuple(row.get("components", ())),
            )
        )
        seen_roles.add(role)
        seen_ids.add(resource_id)
    if seen_roles != REQUIRED_ROLES:
        issues.append(_issue("BRC012_REQUIRED_ROLE_MISSING", "binding"))
    return sorted(result, key=lambda item: (item.role, item.resource_id))


def _manifest_schema_valid(manifest: dict[str, Any]) -> bool:
    """Apply the checksum-closed v6 binding schema before resource admission."""

    try:
        schema = json.loads(
            tome_student_consumption_v6_contract_asset_path(
                "schemas/behavioral_resource_binding_v1.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(manifest)
    except (OSError, ValueError, json.JSONDecodeError, ValidationError):
        return False
    return True


def _components_match(root: Path, components: Any) -> bool:
    """Require raw integrity evidence for every logical NPY component."""

    if not isinstance(components, list) or not components:
        return False
    for component in components:
        if not isinstance(component, dict):
            return False
        locator = component.get("locator")
        digest = component.get("raw_sha256")
        size = component.get("raw_size_bytes")
        if (
            not isinstance(locator, str)
            or not _v1._safe(locator)
            or not _identity_syntax(digest)
            or type(size) is not int
            or size < 0
            or not _raw_matches(root / locator, digest, size)
        ):
            return False
    return True


def _resource_semantic_identity(
    root: Path, row: dict[str, Any], issues: list[BehavioralResourceIssue]
) -> str | None:
    role, encoding, locator = row["role"], row.get("encoding"), row["locator"]
    if encoding == "m7_tome_archive":
        if role != "selected_exemplar_payload":
            issues.append(_issue("BRC013_ENCODING_INVALID", "encoding"))
            return None
        try:
            with open_streaming_tome(root / locator) as reader:
                for _ in reader:
                    pass
                if reader.verification_state != "fully_verified":
                    raise M7ContractError("payload_sequence_digest_mismatch")
                return sha256_identity(
                    canonical_json_bytes(reader.descriptor.semantic_identity)
                )
        except (M7ContractError, OSError, ValueError):
            issues.append(_issue("BRC030_M7_STREAM_INVALID", "exemplar"))
            return None
    if encoding == "json":
        value = _read_json(root / locator, issues, "encoding")
        if value is None:
            return None
        if role == "corridor_mode_table":
            try:
                modes = value["modes"]
                projection = [
                    {
                        "mode_id": mode["mode_id"],
                        "statistic_names": sorted(mode["statistics"]),
                    }
                    for mode in modes
                ]
                return sha256_identity(canonical_json_bytes({"modes": projection}))
            except (KeyError, TypeError):
                issues.append(_issue("BRC021_CORRIDOR_MODE_INVALID", "corridor"))
                return None
        if role == "authority_reference":
            try:
                return canonical_authority_reference_identity(value)
            except ValueError:
                issues.append(_issue("BRC025_AUTHORITY_REFERENCE_INVALID", "identity"))
                return None
        return sha256_identity(canonical_json_bytes(value))
    if encoding in {"jsonl", "m7_jsonl"}:
        records = _read_jsonl_path(root / locator, issues, "encoding")
        if records is None:
            return None
        if role == "selected_passport_index":
            try:
                return canonical_selected_passport_identity(records)
            except ValueError:
                issues.append(_issue("BRC026_PASSPORT_PROJECTION_INVALID", "identity"))
                return None
        return canonical_record_sequence_identity(role=role, records=records)
    if encoding == "multipart_npy":
        components = row.get("components")
        if not isinstance(components, list):
            issues.append(_issue("BRC013_ENCODING_INVALID", "encoding"))
            return None
        framed: list[dict[str, Any]] = []
        for component in components:
            if not isinstance(component, dict):
                issues.append(_issue("BRC013_ENCODING_INVALID", "encoding"))
                return None
            name, component_locator, axes = (
                component.get("component"),
                component.get("locator"),
                component.get("axes"),
            )
            if (
                not isinstance(name, str)
                or not isinstance(component_locator, str)
                or not _v1._safe(component_locator)
                or not isinstance(axes, list)
                or any(not isinstance(axis, str) for axis in axes)
            ):
                issues.append(_issue("BRC013_ENCODING_INVALID", "encoding"))
                return None
            try:
                array = np.load(root / component_locator, allow_pickle=False)
                identity = canonical_npy_component_identity(
                    role=role, component=name, array=array, axes=tuple(axes)
                )
            except (OSError, ValueError):
                issues.append(_issue("BRC013_ENCODING_INVALID", "encoding"))
                return None
            framed.append({"component": name, "semantic_identity": identity})
        try:
            return canonical_multipart_npy_identity(role=role, components=framed)
        except ValueError:
            issues.append(_issue("BRC013_ENCODING_INVALID", "encoding"))
            return None
    issues.append(_issue("BRC013_ENCODING_INVALID", "encoding"))
    return None


def _validate_target(
    root: Path,
    resource: ResolvedBehavioralResource | None,
    issues: list[BehavioralResourceIssue],
) -> tuple[np.ndarray, np.ndarray] | None:
    if resource is None or resource.encoding != "multipart_npy":
        issues.append(_issue("BRC014_TARGET_INVALID", "encoding"))
        return None
    # The declared members are recomputed above; this fixed layout is the v6
    # public target representation, never a permissive filename convention.
    try:
        members = {item["component"]: item["locator"] for item in resource.components}
        input_ids = np.load(root / members["input_ids"], allow_pickle=False)
        mask = np.load(root / members["attention_mask"], allow_pickle=False)
    except (OSError, ValueError):
        issues.append(_issue("BRC014_TARGET_INVALID", "encoding"))
        return None
    if (
        input_ids.dtype != np.dtype("int32")
        or mask.dtype != np.dtype("int8")
        or input_ids.ndim != 2
        or mask.shape != input_ids.shape
        or not np.isin(mask, [0, 1]).all()
    ):
        issues.append(_issue("BRC014_TARGET_INVALID", "encoding"))
        return None
    # A mask is right padded iff no zero is followed by a one in a row.
    if np.any((mask[:, :-1] == 0) & (mask[:, 1:] == 1)):
        issues.append(_issue("BRC015_PADDING_INVALID", "structural_join"))
        return None
    return input_ids, mask


def _validate_assignment(
    root: Path,
    resource: ResolvedBehavioralResource | None,
    target: tuple[np.ndarray, np.ndarray] | None,
    declared_mode_ids: set[int] | None,
    issues: list[BehavioralResourceIssue],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    if resource is None or target is None or resource.encoding != "multipart_npy":
        issues.append(_issue("BRC016_ASSIGNMENT_INVALID", "encoding"))
        return None
    try:
        members = {item["component"]: item["locator"] for item in resource.components}
        arrays = tuple(
            np.load(root / members[name], allow_pickle=False)
            for name in ("example_index", "position", "mode_id", "weight")
        )
    except (OSError, ValueError):
        issues.append(_issue("BRC016_ASSIGNMENT_INVALID", "encoding"))
        return None
    example, position, mode_id, weight = arrays
    count = target[0].size
    if (
        any(array.ndim != 1 or len(array) != count for array in arrays)
        or example.dtype != np.dtype("int32")
        or position.dtype != np.dtype("int32")
        or mode_id.dtype != np.dtype("int32")
        or weight.dtype != np.dtype("float32")
        or not np.isfinite(weight).all()
        or np.any(weight < 0)
    ):
        issues.append(_issue("BRC016_ASSIGNMENT_INVALID", "encoding"))
        return None
    if declared_mode_ids is None or any(
        int(value) not in declared_mode_ids for value in mode_id
    ):
        issues.append(_issue("BRC028_ASSIGNMENT_MODE_UNKNOWN", "corridor"))
        return None
    n, length = target[0].shape
    expected_example = np.repeat(np.arange(n, dtype=np.int32), length)
    expected_position = np.tile(np.arange(length, dtype=np.int32), n)
    if not np.array_equal(example, expected_example) or not np.array_equal(
        position, expected_position
    ):
        issues.append(_issue("BRC017_ASSIGNMENT_GRID_INVALID", "structural_join"))
        return None
    return arrays  # type: ignore[return-value]


def _validate_selected_coordinates(
    target: tuple[np.ndarray, np.ndarray] | None,
    examples: list[dict[str, Any]] | None,
    assignment: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None,
    passports: list[dict[str, Any]] | None,
    exemplars: list[dict[str, Any]] | None,
    vocabulary_size: int,
    issues: list[BehavioralResourceIssue],
) -> None:
    if (
        target is None
        or examples is None
        or assignment is None
        or passports is None
        or exemplars is None
    ):
        return
    ids = [row.get("example_id") for row in examples]
    if len(ids) != target[0].shape[0] or any(
        not isinstance(value, str) for value in ids
    ):
        issues.append(_issue("BRC018_EXAMPLE_REGISTRY_INVALID", "structural_join"))
        return
    index = {value: offset for offset, value in enumerate(ids)}
    if len(index) != len(ids):
        issues.append(_issue("BRC018_EXAMPLE_REGISTRY_INVALID", "structural_join"))
        return
    seen: set[tuple[str, int]] = set()
    assignment_modes = {
        (ids[int(example_index)], int(position)): int(mode_id)
        for example_index, position, mode_id in zip(
            assignment[0], assignment[1], assignment[2], strict=True
        )
    }
    for record in passports:
        key = _selected_key(record)
        if key is None or key in seen or key[0] not in index:
            issues.append(_issue("BRC019_SELECTED_JOIN_INVALID", "structural_join"))
            continue
        seen.add(key)
        row, position = index[key[0]], key[1]
        if position >= target[0].shape[1] or target[1][row, position] != 1:
            issues.append(
                _issue("BRC020_SELECTED_MASKED_OR_OUT_OF_RANGE", "structural_join")
            )
        elif record.get("corridor_mode_id") != assignment_modes[key]:
            issues.append(_issue("BRC029_SELECTED_MODE_MISMATCH", "corridor"))
    exemplar_keys = {_selected_key(record) for record in exemplars}
    if None in exemplar_keys or exemplar_keys != seen:
        issues.append(_issue("BRC019_SELECTED_JOIN_INVALID", "exemplar"))
        return
    corridor_coordinates = {
        (ids[int(example_index)], int(position))
        for example_index, position in zip(assignment[0], assignment[1], strict=True)
    }
    findings = validate_exemplar_passport_semantics(
        passports,
        exemplars,
        corridor_coordinates=corridor_coordinates,
        vocabulary_size=vocabulary_size,
    )
    if findings:
        issues.append(
            _issue(
                "BRC027_EXEMPLAR_SEMANTICS_INVALID",
                "exemplar",
                findings=[finding.code for finding in findings],
            )
        )


def _validate_m7_selected_exemplars(
    root: Path,
    resource: ResolvedBehavioralResource,
    target: tuple[np.ndarray, np.ndarray] | None,
    examples: list[dict[str, Any]] | None,
    assignment: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None,
    passports: list[dict[str, Any]] | None,
    vocabulary_size: int,
    issues: list[BehavioralResourceIssue],
) -> None:
    """Validate M7 payload semantics incrementally without retaining records."""

    if target is None or examples is None or assignment is None or passports is None:
        return
    ids = [row.get("example_id") for row in examples]
    if len(ids) != target[0].shape[0] or any(
        not isinstance(value, str) for value in ids
    ):
        issues.append(_issue("BRC018_EXAMPLE_REGISTRY_INVALID", "structural_join"))
        return
    example_index = {value: offset for offset, value in enumerate(ids)}
    if len(example_index) != len(ids):
        issues.append(_issue("BRC018_EXAMPLE_REGISTRY_INVALID", "structural_join"))
        return
    passport_by_key = {_selected_key(record): record for record in passports}
    if None in passport_by_key or len(passport_by_key) != len(passports):
        issues.append(_issue("BRC019_SELECTED_JOIN_INVALID", "structural_join"))
        return
    assignment_modes = {
        (ids[int(row)], int(position)): int(mode)
        for row, position, mode in zip(
            assignment[0], assignment[1], assignment[2], strict=True
        )
    }
    corridor_coordinates = set(assignment_modes)
    seen: set[tuple[str, int]] = set()
    try:
        with _staged_verified_m7_archive(root, resource) as archive:
            reader = open_streaming_tome(archive)
            try:
                for exemplar in reader:
                    key = _selected_key(exemplar)
                    passport = passport_by_key.get(key)
                    if (
                        key is None
                        or passport is None
                        or key in seen
                        or key[0] not in example_index
                    ):
                        issues.append(
                            _issue("BRC019_SELECTED_JOIN_INVALID", "exemplar")
                        )
                        continue
                    seen.add(key)
                    row, position = example_index[key[0]], key[1]
                    if position >= target[0].shape[1] or target[1][row, position] != 1:
                        issues.append(
                            _issue(
                                "BRC020_SELECTED_MASKED_OR_OUT_OF_RANGE",
                                "structural_join",
                            )
                        )
                    elif exemplar.get("corridor_mode_id") != assignment_modes[key]:
                        issues.append(
                            _issue("BRC029_SELECTED_MODE_MISMATCH", "corridor")
                        )
                    normalized = dict(exemplar)
                    normalized["rank"] = 1
                    findings = validate_exemplar_passport_semantics(
                        [passport],
                        [normalized],
                        corridor_coordinates=corridor_coordinates,
                        vocabulary_size=vocabulary_size,
                    )
                    if findings:
                        issues.append(
                            _issue(
                                "BRC027_EXEMPLAR_SEMANTICS_INVALID",
                                "exemplar",
                                findings=[finding.code for finding in findings],
                            )
                        )
            finally:
                reader.close()
            if reader.verification_state != "fully_verified":
                issues.append(_issue("BRC030_M7_STREAM_INVALID", "exemplar"))
    except (M7ContractError, OSError, ValueError):
        issues.append(_issue("BRC030_M7_STREAM_INVALID", "exemplar"))
        return
    if seen != set(passport_by_key):
        issues.append(_issue("BRC019_SELECTED_JOIN_INVALID", "exemplar"))


def _validate_mode_table(
    root: Path,
    resource: ResolvedBehavioralResource | None,
    issues: list[BehavioralResourceIssue],
) -> set[int] | None:
    if resource is None:
        return None
    table = _read_json(root / resource.locator, issues, "corridor")
    if table is None:
        return None
    modes = table.get("modes")
    if not isinstance(modes, list) or not modes:
        issues.append(_issue("BRC021_CORRIDOR_MODE_INVALID", "corridor"))
        return None
    required = {"entropy", "top1_margin", "top8_mass", "top32_mass", "tail_mass"}
    for mode in modes:
        stats = mode.get("statistics") if isinstance(mode, dict) else None
        if not isinstance(stats, dict) or set(stats) != required:
            issues.append(_issue("BRC021_CORRIDOR_MODE_INVALID", "corridor"))
            return None
        try:
            values = {name: stats[name] for name in required}
            if any(
                not isinstance(value, dict)
                or not all(_finite(value.get(key)) for key in ("min", "mean", "max"))
                or value["min"] > value["mean"] > value["max"]
                for value in values.values()
            ):
                raise ValueError
            if any(
                values[name][key] < 0 or values[name][key] > 1
                for name in {"top1_margin", "top8_mass", "top32_mass", "tail_mass"}
                for key in ("min", "mean", "max")
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            issues.append(_issue("BRC021_CORRIDOR_MODE_INVALID", "corridor"))
            return None
    mode_ids = [mode.get("mode_id") for mode in modes]
    if any(type(mode_id) is not int or mode_id < 0 for mode_id in mode_ids) or len(
        set(mode_ids)
    ) != len(mode_ids):
        issues.append(_issue("BRC021_CORRIDOR_MODE_INVALID", "corridor"))
        return None
    return set(mode_ids)


def _validate_delivery_receipt(
    root: Path,
    resource: ResolvedBehavioralResource | None,
    issues: list[BehavioralResourceIssue],
) -> None:
    if resource is None:
        return
    receipt = _read_json(root / resource.locator, issues, "provenance")
    if receipt is None:
        return
    if receipt.get("delivery_path") not in {
        "one_pass_pruned_candidate",
        "two_pass_rerun_selected",
        "one_pass_full",
    }:
        issues.append(_issue("BRC022_DELIVERY_RECEIPT_INVALID", "provenance"))


def _read_json(
    path: Path, issues: list[BehavioralResourceIssue], phase: str
) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        issues.append(_issue("BRC023_JSON_INVALID", phase, locator=str(path)))
        return None


def _read_jsonl(
    root: Path,
    resource: ResolvedBehavioralResource | None,
    issues: list[BehavioralResourceIssue],
) -> list[dict[str, Any]] | None:
    if resource is None:
        return None
    return _read_jsonl_path(root / resource.locator, issues, "encoding")


def _read_jsonl_path(
    path: Path, issues: list[BehavioralResourceIssue], phase: str
) -> list[dict[str, Any]] | None:
    try:
        rows = [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        ]
        if not rows or any(not isinstance(row, dict) for row in rows):
            raise ValueError
        return rows
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        issues.append(_issue("BRC024_JSONL_INVALID", phase, locator=str(path)))
        return None


def _parse_jsonl_bytes(payload: bytes) -> tuple[dict[str, Any], ...]:
    """Parse one nonempty ordinary JSONL member after its trust transition."""

    try:
        decoded = payload.decode("utf-8")
        lines = decoded.splitlines()
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("JSONL decoding failed") from exc
    if not lines or any(not line for line in lines):
        raise ValueError("JSONL must contain nonempty object records")
    try:
        records = tuple(json.loads(line) for line in lines)
    except json.JSONDecodeError as exc:
        raise ValueError("JSONL decoding failed") from exc
    if any(not isinstance(record, dict) for record in records):
        raise ValueError("JSONL must contain nonempty object records")
    return records


def _find_resource(
    descriptor: BehavioralAuthorityDescriptor, resource_id: str
) -> ResolvedBehavioralResource | None:
    return next(
        (
            item
            for item in (
                *descriptor.authority_resources,
                *descriptor.non_authority_resources,
            )
            if item.resource_id == resource_id
        ),
        None,
    )


def _verified_resource_bytes(root: Path, resource: ResolvedBehavioralResource) -> bytes:
    """Make the raw-byte trust transition once and retain immutable bytes."""

    path = root / resource.locator
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValueError("v6 behavioral resource is unavailable at open") from exc
    if (
        len(payload) != resource.raw_size_bytes
        or sha256_identity(payload) != resource.raw_sha256
    ):
        raise ValueError("v6 behavioral resource integrity changed at open")
    return payload


def _raw_matches(path: Path, digest: str, size: int) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    observed, observed_size = _chunked_file_identity(path)
    return observed_size == size and observed == digest


def _chunked_file_identity(path: Path) -> tuple[str, int]:
    """Hash a member in fixed-size blocks without materializing its content."""

    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return "sha256:" + digest.hexdigest(), size


@contextmanager
def _staged_verified_m7_archive(
    root: Path,
    resource: ResolvedBehavioralResource,
) -> Iterator[Path]:
    """Create an immutable, chunk-verified M7 snapshot for one opener call."""

    source = root / resource.locator
    with tempfile.TemporaryDirectory(prefix="radjax-contract-v6-m7-") as temporary:
        staged = Path(temporary) / "payload.tgz"
        digest = hashlib.sha256()
        size = 0
        try:
            with source.open("rb") as reader, staged.open("wb") as writer:
                while block := reader.read(1024 * 1024):
                    digest.update(block)
                    size += len(block)
                    writer.write(block)
        except OSError as exc:
            raise ValueError("v6 M7 resource is unavailable at open") from exc
        if (
            size != resource.raw_size_bytes
            or "sha256:" + digest.hexdigest() != resource.raw_sha256
        ):
            raise ValueError("v6 M7 resource integrity changed at open")
        yield staged


def _registry(resources: list[ResolvedBehavioralResource]) -> list[dict[str, str]]:
    return [
        {
            "resource_id": item.resource_id,
            "role": item.role,
            "schema": item.schema,
            "semantic_identity": item.semantic_identity,
        }
        for item in resources
    ]


def _selected_key(record: dict[str, Any]) -> tuple[str, int] | None:
    identifier, position = (
        record.get("selected_example_id"),
        record.get("selected_position"),
    )
    if not isinstance(identifier, str) or type(position) is not int or position < 0:
        return None
    return identifier, position


def _identity_syntax(value: Any) -> bool:
    try:
        _require_identity(value)
    except ValueError:
        return False
    return True


def _issue(code: str, phase: str, **context: Any) -> BehavioralResourceIssue:
    return BehavioralResourceIssue(code, phase, PROFILE_ID, context)


def _result(
    issues: list[BehavioralResourceIssue],
    warnings: list[BehavioralResourceIssue],
    descriptor: BehavioralAuthorityDescriptor | None = None,
    language_binding: LanguageTokenizerBindingDescriptor | None = None,
) -> BehavioralAuthorityValidationResult:
    order = {phase: index for index, phase in enumerate(_PHASES)}
    ordered = tuple(
        sorted(issues, key=lambda item: (order.get(item.phase, 99), item.code))
    )
    return BehavioralAuthorityValidationResult(
        not ordered,
        PROFILE_ID,
        ordered,
        tuple(warnings),
        descriptor if not ordered else None,
        language_binding if not ordered else None,
    )
