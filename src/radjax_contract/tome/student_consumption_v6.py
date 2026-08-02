"""Additive behavioral-resource authority for ``native_v3_student_v6``.

V6 deliberately composes the immutable V5 language/tokenizer binding with a
closed, architecture-neutral behavioral registry.  This module owns canonical
logical identities; physical package admission and verified opening are added
below these primitives so a delivery locator can never influence behavioral
replay equivalence.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from radjax_contract.tome.language_tokenizer_binding_v1 import canonical_json_bytes

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
_PASSPORT_FIELDS = (
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
_AUTHORITY_REFERENCE_FIELDS = (
    "schema_version",
    "selection_integration_config_hash",
    "score_pass_authority_hash",
    "delivery_authority_hash",
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
    """Hash only the frozen authority projection of canonical passport rows."""

    projected: list[dict[str, Any]] = []
    for expected_rank, record in enumerate(records, start=1):
        if set(record) != set(_PASSPORT_FIELDS):
            raise ValueError("selected passport fields are closed")
        if (
            record["schema_version"] != "radjax_selected_passport_v6"
            or record["rank"] != expected_rank
            or record["corridor_assignment_status"] != "selected"
            or not isinstance(record["selected_example_id"], str)
            or not record["selected_example_id"]
            or any(
                type(record[name]) is not int or record[name] < 0
                for name in ("selected_position", "corridor_mode_id")
            )
            or not _finite(record["selected_score"])
            or not isinstance(record["selected_policy"], str)
            or not isinstance(record["corridor_fingerprint_id"], str)
            or not _identity_syntax(record["selection_integration_config_hash"])
        ):
            raise ValueError("selected passport projection is invalid")
        projected.append({name: record[name] for name in _PASSPORT_FIELDS})
    if not projected or projected != sorted(
        projected,
        key=lambda item: (
            item["rank"],
            item["selected_example_id"],
            item["selected_position"],
        ),
    ):
        raise ValueError("selected passports must have deterministic rank order")
    return canonical_record_sequence_identity(
        role="selected_passport_index", records=projected
    )


def canonical_authority_reference_identity(reference: dict[str, Any]) -> str:
    """Hash the exact closed v6 score/selection/delivery authority object."""

    if (
        set(reference) != set(_AUTHORITY_REFERENCE_FIELDS)
        or reference["schema_version"] != "radjax_behavioral_authority_reference_v6"
        or any(
            not _identity_syntax(reference[name])
            for name in _AUTHORITY_REFERENCE_FIELDS[1:]
        )
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


def _identity_syntax(value: Any) -> bool:
    try:
        _require_identity(value)
    except ValueError:
        return False
    return True


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
