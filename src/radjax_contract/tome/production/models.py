from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

KNOWN_CONTENT_ROLES = frozenset(
    {
        "target_store_metadata",
        "vocab_contract",
        "teacher_manifest",
        "emission_config",
        "validation_report",
        "target_shard",
        "corridor_summary",
        "corridor_mode_table",
        "corridor_assignment_manifest",
        "corridor_assignment_position_example_index",
        "corridor_assignment_position",
        "corridor_assignment_mode_id",
        "corridor_assignment_weight",
        "corridor_assignment_examples_metadata",
        "corridor_assignment_fingerprint_index",
        "corridor_fingerprints",
        "corridor_human_summary",
        "selected_exemplar_index",
        "selected_exemplar_payload_shard",
        "exemplar_delivery_report",
        "exemplar_leaderboard_report",
    }
)


@dataclass(frozen=True)
class ArtifactLocalModeId:
    value: int | str

    @classmethod
    def from_value(cls, value: Any) -> ArtifactLocalModeId:
        return cls(_artifact_local_id(value, "mode_id"))


@dataclass(frozen=True)
class ArtifactLocalFingerprintId:
    value: int | str

    @classmethod
    def from_value(cls, value: Any) -> ArtifactLocalFingerprintId:
        return cls(_artifact_local_id(value, "fingerprint_id"))


@dataclass(frozen=True)
class ProductionTomeIdentity:
    artifact_kind: str
    cover_page_version: int
    tome_version: int
    layout: str
    source_artifact_type: str
    created_by: str
    created_at: str


@dataclass(frozen=True)
class ProductionTomeContentRef:
    role: str
    path: str
    sha256: str
    size_bytes: int
    required: bool
    classification: str
    known_role: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProductionTomeContentRef:
        role = str(payload["role"])
        known = {
            "role",
            "path",
            "sha256",
            "size_bytes",
            "required",
            "classification",
        }
        return cls(
            role=role,
            path=str(payload["path"]),
            sha256=str(payload["sha256"]),
            size_bytes=int(payload["size_bytes"]),
            required=_required_bool(payload, "required"),
            classification=str(payload["classification"]),
            known_role=role in KNOWN_CONTENT_ROLES,
            metadata=_unknown(payload, known),
        )


@dataclass(frozen=True)
class ProductionTomeProducerValidation:
    status: str
    validated_by: str
    validation_report_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductionTomeProvenance:
    teacher: dict[str, Any]
    tokenizer: dict[str, Any]
    targets: dict[str, Any]
    corpus: dict[str, Any] | None
    teacher_model: dict[str, Any] | None


@dataclass(frozen=True)
class BehavioralSurfaceContract:
    surface_id: str
    surface_kind: str
    schema_version: str
    required_content_roles: tuple[str, ...]
    optional_content_roles: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    prerequisites: tuple[str, ...]
    target_scope: dict[str, Any]
    semantics: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BehavioralSurfaceContract:
        known = {
            "surface_id",
            "surface_kind",
            "schema_version",
            "required_content_roles",
            "optional_content_roles",
            "required_capabilities",
            "prerequisites",
            "target_scope",
            "semantics",
        }
        return cls(
            surface_id=str(payload["surface_id"]),
            surface_kind=str(payload["surface_kind"]),
            schema_version=str(payload["schema_version"]),
            required_content_roles=_string_tuple(
                payload["required_content_roles"],
                "required_content_roles",
            ),
            optional_content_roles=_string_tuple(
                payload["optional_content_roles"],
                "optional_content_roles",
            ),
            required_capabilities=_string_tuple(
                payload["required_capabilities"],
                "required_capabilities",
            ),
            prerequisites=_string_tuple(payload["prerequisites"], "prerequisites"),
            target_scope=dict(payload["target_scope"]),
            semantics=dict(payload["semantics"]),
            metadata=_unknown(payload, known),
        )


@dataclass(frozen=True)
class TrainingPassRecommendation:
    pass_id: str
    surface_id: str
    checkpoint_after: bool
    prerequisites: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TrainingPassRecommendation:
        known = {
            "pass_id",
            "surface_id",
            "checkpoint_after",
            "prerequisites",
            "required_capabilities",
        }
        return cls(
            pass_id=str(payload["pass_id"]),
            surface_id=str(payload["surface_id"]),
            checkpoint_after=_required_bool(payload, "checkpoint_after"),
            prerequisites=_string_tuple(payload["prerequisites"], "prerequisites"),
            required_capabilities=_string_tuple(
                payload["required_capabilities"],
                "required_capabilities",
            ),
            metadata=_unknown(payload, known),
        )


@dataclass(frozen=True)
class RecommendedTrainingPlan:
    schema_version: str
    passes: tuple[TrainingPassRecommendation, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RecommendedTrainingPlan:
        passes = payload["passes"]
        if not isinstance(passes, list):
            raise ValueError("recommended_training_plan.passes must be a list")
        return cls(
            schema_version=str(payload["schema_version"]),
            passes=tuple(
                TrainingPassRecommendation.from_dict(dict(item)) for item in passes
            ),
        )


@dataclass(frozen=True)
class ProductionTomeCoverPage:
    identity: ProductionTomeIdentity
    contents: tuple[ProductionTomeContentRef, ...]
    provenance: ProductionTomeProvenance
    producer_validation: ProductionTomeProducerValidation
    claims_not_made: tuple[str, ...]
    surfaces: tuple[BehavioralSurfaceContract, ...]
    recommended_training_plan: RecommendedTrainingPlan
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProductionTomeCoverPage:
        contents = payload["contents"]
        surfaces = payload["behavioral_surfaces"]
        validation = dict(payload["validation"])
        if not isinstance(contents, list):
            raise ValueError("cover_page.contents must be a list")
        if not isinstance(surfaces, list):
            raise ValueError("cover_page.behavioral_surfaces must be a list")
        known = {
            "artifact_kind",
            "cover_page_version",
            "tome_version",
            "layout",
            "source_artifact_type",
            "created_by",
            "created_at",
            "teacher",
            "tokenizer",
            "targets",
            "corpus",
            "teacher_model_provenance",
            "contents",
            "validation",
            "claims_not_made",
            "behavioral_surfaces",
            "recommended_training_plan",
        }
        return cls(
            identity=ProductionTomeIdentity(
                artifact_kind=str(payload["artifact_kind"]),
                cover_page_version=int(payload["cover_page_version"]),
                tome_version=int(payload["tome_version"]),
                layout=str(payload["layout"]),
                source_artifact_type=str(payload["source_artifact_type"]),
                created_by=str(payload["created_by"]),
                created_at=str(payload["created_at"]),
            ),
            contents=tuple(
                ProductionTomeContentRef.from_dict(dict(item)) for item in contents
            ),
            provenance=ProductionTomeProvenance(
                teacher=dict(payload["teacher"]),
                tokenizer=dict(payload["tokenizer"]),
                targets=dict(payload["targets"]),
                corpus=(
                    None if payload.get("corpus") is None else dict(payload["corpus"])
                ),
                teacher_model=(
                    None
                    if payload.get("teacher_model_provenance") is None
                    else dict(payload["teacher_model_provenance"])
                ),
            ),
            producer_validation=ProductionTomeProducerValidation(
                status=str(validation["status"]),
                validated_by=str(validation["validated_by"]),
                validation_report_path=str(validation["validation_report_path"]),
                metadata=_unknown(
                    validation,
                    {"status", "validated_by", "validation_report_path"},
                ),
            ),
            claims_not_made=_claims(payload.get("claims_not_made", [])),
            surfaces=tuple(
                BehavioralSurfaceContract.from_dict(dict(item)) for item in surfaces
            ),
            recommended_training_plan=RecommendedTrainingPlan.from_dict(
                dict(payload["recommended_training_plan"])
            ),
            metadata=_unknown(payload, known),
        )


@dataclass(frozen=True)
class StatBounds:
    minimum: float
    maximum: float
    mean: float | None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StatBounds:
        return cls(
            minimum=float(payload["min"]),
            maximum=float(payload["max"]),
            mean=None if payload.get("mean") is None else float(payload["mean"]),
        )


@dataclass(frozen=True)
class CorridorMode:
    mode_id: ArtifactLocalModeId
    mode_key: dict[str, Any]
    name: str | None
    description: str | None
    count: int
    share: float
    bounds: dict[str, StatBounds]
    mode_policy: str
    representative_metadata: tuple[dict[str, Any], ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CorridorMode:
        bounds = payload["bounds"]
        if not isinstance(bounds, dict):
            raise ValueError("corridor mode bounds must be an object")
        representatives = payload.get("representative_examples", [])
        if not isinstance(representatives, list):
            raise ValueError("representative_examples must be a list")
        known = {
            "mode_id",
            "mode_key",
            "name",
            "description",
            "record_count",
            "count",
            "share",
            "bounds",
            "representative_examples",
            "mode_policy",
        }
        return cls(
            mode_id=ArtifactLocalModeId.from_value(payload["mode_id"]),
            mode_key=dict(payload["mode_key"]),
            name=None if payload.get("name") is None else str(payload["name"]),
            description=(
                None
                if payload.get("description") is None
                else str(payload["description"])
            ),
            count=int(payload.get("count", payload.get("record_count", 0))),
            share=float(payload.get("share", 0.0)),
            bounds={
                str(name): StatBounds.from_dict(dict(value))
                for name, value in bounds.items()
            },
            mode_policy=str(payload["mode_policy"]),
            representative_metadata=tuple(dict(item) for item in representatives),
            metadata=_unknown(payload, known),
        )


@dataclass(frozen=True)
class CorridorSummary:
    observation_basis: str
    degraded: bool
    mode_policy: str
    tracked_stats: tuple[str, ...]
    mode_count: int
    fingerprint_count: int
    assignment_storage_kind: str
    assignment_count: int
    selected_exemplars_linked: bool
    corridor_stat_top_k: int

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CorridorSummary:
        return cls(
            observation_basis=str(payload["corridor_observation_basis"]),
            degraded=_required_bool(payload, "degraded_corridor_export"),
            mode_policy=str(
                payload.get("corridor_mode_policy", payload.get("mode_policy", ""))
            ),
            tracked_stats=_string_tuple(
                payload["corridor_tracked_stats"],
                "corridor_tracked_stats",
            ),
            mode_count=int(payload["mode_count"]),
            fingerprint_count=int(payload["fingerprint_count"]),
            assignment_storage_kind=str(payload["corridor_assignment_storage_kind"]),
            assignment_count=int(payload["corridor_assignment_count"]),
            selected_exemplars_linked=_required_bool(
                payload,
                "selected_exemplars_linked_to_corridor_modes",
            ),
            corridor_stat_top_k=int(payload["corridor_stat_top_k"]),
        )


@dataclass(frozen=True)
class PackedArrayDescriptor:
    path: str
    dtype: str
    shape: tuple[int, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PackedArrayDescriptor:
        shape = payload["shape"]
        if not isinstance(shape, list):
            raise ValueError("packed array shape must be a list")
        return cls(
            path=str(payload["path"]),
            dtype=str(payload["dtype"]),
            shape=tuple(int(item) for item in shape),
        )


@dataclass(frozen=True)
class CorridorAssignmentManifest:
    schema_version: str
    storage_kind: str
    assignment_policy: str
    observation_basis: str
    assignment_count: int
    example_count: int
    arrays: dict[str, PackedArrayDescriptor]
    examples_metadata_path: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CorridorAssignmentManifest:
        arrays = payload["arrays"]
        examples = payload["examples_metadata"]
        if not isinstance(arrays, dict) or not isinstance(examples, dict):
            raise ValueError("packed assignment descriptors must be objects")
        return cls(
            schema_version=str(payload["schema_version"]),
            storage_kind=str(payload["storage_kind"]),
            assignment_policy=str(payload["assignment_policy"]),
            observation_basis=str(payload["corridor_observation_basis"]),
            assignment_count=int(payload["num_assignments"]),
            example_count=int(payload["num_examples"]),
            arrays={
                str(name): PackedArrayDescriptor.from_dict(dict(value))
                for name, value in arrays.items()
            },
            examples_metadata_path=str(examples["path"]),
        )


@dataclass(frozen=True)
class CorridorContract:
    surface: BehavioralSurfaceContract
    summary: CorridorSummary
    modes: tuple[CorridorMode, ...]
    assignments: CorridorAssignmentManifest


@dataclass(frozen=True)
class SelectedExemplarIndexEntry:
    example_id: str
    selected_position: int
    selected_score: float
    rank: int | None
    selected_policy: str
    corridor_mode_id: ArtifactLocalModeId
    corridor_fingerprint_id: ArtifactLocalFingerprintId | None
    linkage_status: str
    delivery_path: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SelectedExemplarIndexEntry:
        return cls(
            example_id=str(payload["selected_example_id"]),
            selected_position=int(payload["selected_position"]),
            selected_score=float(payload["selected_score"]),
            rank=None if payload.get("rank") is None else int(payload["rank"]),
            selected_policy=str(payload["selected_policy"]),
            corridor_mode_id=ArtifactLocalModeId.from_value(
                payload["corridor_mode_id"]
            ),
            corridor_fingerprint_id=(
                None
                if payload.get("corridor_fingerprint_id") is None
                else ArtifactLocalFingerprintId.from_value(
                    payload["corridor_fingerprint_id"]
                )
            ),
            linkage_status=str(payload["corridor_assignment_status"]),
            delivery_path=str(payload["source_delivery_path"]),
        )


@dataclass(frozen=True)
class SelectedExemplarPayload:
    index: SelectedExemplarIndexEntry
    top_token_ids: tuple[int, ...]
    top_log_probs: tuple[float, ...]
    top_probs: tuple[float, ...]
    selection_mask: tuple[bool, ...]
    effective_top_k: int
    top_mass: float
    tail_mass: float
    bucket_masses: tuple[float, ...]
    teacher_entropy: float
    sequence_length: int
    vocab_size: int
    bucket_count: int
    dynamic_top_k: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SelectedExemplarPayload:
        return cls(
            index=SelectedExemplarIndexEntry.from_dict(payload),
            top_token_ids=tuple(int(item) for item in payload["top_token_ids"]),
            top_log_probs=tuple(float(item) for item in payload["top_log_probs"]),
            top_probs=tuple(float(item) for item in payload["top_probs"]),
            selection_mask=tuple(
                _strict_bool(item, "top_selection_mask")
                for item in payload["top_selection_mask"]
            ),
            effective_top_k=int(payload["effective_top_k"]),
            top_mass=float(payload["top_mass"]),
            tail_mass=float(payload["tail_mass"]),
            bucket_masses=tuple(float(item) for item in payload["bucket_masses"]),
            teacher_entropy=float(payload["teacher_entropy"]),
            sequence_length=int(payload["sequence_length"]),
            vocab_size=int(payload["vocab_size"]),
            bucket_count=int(payload["num_buckets"]),
            dynamic_top_k=dict(payload["dynamic_top_k"]),
        )


@dataclass(frozen=True)
class ExemplarContract:
    surface: BehavioralSurfaceContract
    selected_index: tuple[SelectedExemplarIndexEntry, ...]
    payloads: tuple[SelectedExemplarPayload, ...]
    delivery_paths: tuple[str, ...]


@dataclass(frozen=True)
class ProductionTomeArtifact:
    cover_page: ProductionTomeCoverPage
    corridor: CorridorContract | None
    exemplar: ExemplarContract | None


def _artifact_local_id(value: Any, field_name: str) -> int | str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{field_name} must be an integer or string")
    if isinstance(value, str) and not value:
        raise ValueError(f"{field_name} must be nonempty")
    return value


def _strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be boolean")
    return value


def _required_bool(payload: dict[str, Any], field_name: str) -> bool:
    return _strict_bool(payload[field_name], field_name)


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    result = tuple(str(item) for item in value)
    if any(not item for item in result):
        raise ValueError(f"{field_name} must contain nonempty strings")
    return result


def _claims(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted(str(key) for key, enabled in value.items() if enabled))
    raise ValueError("claims_not_made must be a list or object")


def _unknown(payload: dict[str, Any], known: set[str]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in known}
