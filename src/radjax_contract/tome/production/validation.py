from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

from radjax_contract.tome.production.models import (
    ArtifactLocalModeId,
    BehavioralSurfaceContract,
    CorridorAssignmentManifest,
    CorridorContract,
    CorridorMode,
    CorridorSummary,
    ExemplarContract,
    ProductionTomeArtifact,
    ProductionTomeContentRef,
    ProductionTomeCoverPage,
    SelectedExemplarIndexEntry,
    SelectedExemplarPayload,
)

_CLASSIFICATIONS = frozenset(
    {
        "training_critical",
        "integrity_or_provenance",
        "diagnostic",
        "human_readable",
        "operational",
    }
)
_CORE_REQUIRED_ROLES = frozenset(
    {
        "target_store_metadata",
        "vocab_contract",
        "teacher_manifest",
        "emission_config",
        "validation_report",
        "target_shard",
    }
)
_MULTI_VALUE_ROLES = frozenset({"target_shard", "selected_exemplar_payload_shard"})
_TRACKED_STATS = (
    "entropy",
    "top1_margin",
    "top8_mass",
    "top32_mass",
    "tail_mass",
)
_ARRAY_ROLES = {
    "position_example_index": "corridor_assignment_position_example_index",
    "position": "corridor_assignment_position",
    "mode_id": "corridor_assignment_mode_id",
    "weight": "corridor_assignment_weight",
    "fingerprint_index": "corridor_assignment_fingerprint_index",
}


@dataclass(frozen=True)
class ProductionTomeValidationResult:
    artifact: ProductionTomeArtifact | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.blockers

    @property
    def status(self) -> str:
        return "pass" if self.ok else "fail"


def load_production_tome(tome_dir: str | Path) -> ProductionTomeValidationResult:
    """Load and validate a production Tome without inferring unindexed files."""

    return validate_production_tome(tome_dir)


def validate_production_tome(
    tome_dir: str | Path,
) -> ProductionTomeValidationResult:
    root = Path(tome_dir)
    blockers: list[str] = []
    warnings: list[str] = []
    try:
        cover_payload = _read_object(root / "cover_page.json")
        cover = ProductionTomeCoverPage.from_dict(cover_payload)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return ProductionTomeValidationResult(
            artifact=None,
            blockers=(f"cover_page_invalid: {exc}",),
            warnings=(),
        )

    _validate_identity(cover, blockers)
    role_map = _validate_contents(root, cover, blockers, warnings)
    _validate_producer_report(root, cover, role_map, blockers)
    _validate_surfaces_and_plan(cover, role_map, blockers)

    corridor = _load_corridor(root, cover, role_map, blockers)
    exemplar = _load_exemplar(root, cover, role_map, corridor, blockers)
    artifact = ProductionTomeArtifact(
        cover_page=cover,
        corridor=corridor,
        exemplar=exemplar,
    )
    return ProductionTomeValidationResult(
        artifact=artifact,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )


def _validate_identity(
    cover: ProductionTomeCoverPage,
    blockers: list[str],
) -> None:
    expected = {
        "artifact_kind": (cover.identity.artifact_kind, "radjax_tome"),
        "cover_page_version": (cover.identity.cover_page_version, 2),
        "tome_version": (cover.identity.tome_version, 1),
        "layout": (cover.identity.layout, "unpacked_directory"),
    }
    for field_name, (actual, wanted) in expected.items():
        if actual != wanted:
            blockers.append(
                f"identity_mismatch: {field_name} must be {wanted!r}, got {actual!r}"
            )


def _validate_contents(
    root: Path,
    cover: ProductionTomeCoverPage,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, list[ProductionTomeContentRef]]:
    role_map: dict[str, list[ProductionTomeContentRef]] = {}
    seen_paths: set[str] = set()
    root_resolved = root.resolve()
    for ref in cover.contents:
        role_map.setdefault(ref.role, []).append(ref)
        if ref.classification not in _CLASSIFICATIONS:
            blockers.append(
                f"content_classification_invalid: {ref.role} uses "
                f"{ref.classification!r}"
            )
        if not ref.known_role:
            warnings.append(f"unknown_content_role: {ref.role}")
        if ref.path in seen_paths:
            blockers.append(f"content_path_duplicate: {ref.path}")
        seen_paths.add(ref.path)
        if not _is_safe_relative_posix(ref.path):
            blockers.append(f"content_path_unsafe: {ref.path!r}")
            continue
        candidate = root / PurePosixPath(ref.path)
        try:
            candidate.resolve().relative_to(root_resolved)
        except ValueError:
            blockers.append(f"content_path_outside_artifact: {ref.path!r}")
            continue
        if not candidate.is_file():
            blockers.append(f"content_missing: {ref.role} -> {ref.path}")
            continue
        actual_size = candidate.stat().st_size
        if actual_size != ref.size_bytes:
            blockers.append(
                f"content_size_mismatch: {ref.path} expected {ref.size_bytes}, "
                f"got {actual_size}"
            )
        actual_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual_hash != ref.sha256:
            blockers.append(f"content_hash_mismatch: {ref.path}")

    for role in sorted(_CORE_REQUIRED_ROLES):
        refs = role_map.get(role, [])
        if not refs:
            blockers.append(f"required_content_role_missing: {role}")
        elif not all(ref.required for ref in refs):
            blockers.append(f"required_content_role_not_required: {role}")
    for role, refs in sorted(role_map.items()):
        if role not in _MULTI_VALUE_ROLES and len(refs) > 1:
            blockers.append(f"content_role_cardinality_invalid: {role}")
    return role_map


def _validate_producer_report(
    root: Path,
    cover: ProductionTomeCoverPage,
    role_map: dict[str, list[ProductionTomeContentRef]],
    blockers: list[str],
) -> None:
    if cover.producer_validation.status != "pass":
        blockers.append(
            "producer_validation_failed: cover page validation status is not pass"
        )
    report_ref = _single_ref(role_map, "validation_report", blockers)
    if report_ref is None:
        return
    if cover.producer_validation.validation_report_path != report_ref.path:
        blockers.append(
            "producer_validation_report_mismatch: validation report path is not the "
            "indexed validation_report role"
        )
    try:
        report = _read_object(root / PurePosixPath(report_ref.path))
        report_status = str(report["status"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        blockers.append(f"producer_validation_report_invalid: {exc}")
        return
    if report_status != "pass":
        blockers.append(
            f"producer_validation_report_failed: report status is {report_status!r}"
        )
    if report_status != cover.producer_validation.status:
        blockers.append(
            "producer_validation_status_mismatch: cover and report disagree"
        )


def _validate_surfaces_and_plan(
    cover: ProductionTomeCoverPage,
    role_map: dict[str, list[ProductionTomeContentRef]],
    blockers: list[str],
) -> None:
    surface_map: dict[str, BehavioralSurfaceContract] = {}
    for surface in cover.surfaces:
        if not surface.surface_id or surface.surface_id in surface_map:
            blockers.append(
                f"surface_id_invalid: duplicate or empty ID {surface.surface_id!r}"
            )
            continue
        surface_map[surface.surface_id] = surface
        for role in surface.required_content_roles:
            if role not in role_map:
                blockers.append(
                    f"surface_required_role_missing: {surface.surface_id} -> {role}"
                )
            elif not all(ref.required for ref in role_map[role]):
                blockers.append(
                    f"surface_required_role_not_required: {surface.surface_id} -> "
                    f"{role}"
                )
        for prerequisite in surface.prerequisites:
            if prerequisite == surface.surface_id:
                blockers.append(
                    "surface_prerequisite_cycle: "
                    f"{surface.surface_id} references itself"
                )
    for surface in cover.surfaces:
        for prerequisite in surface.prerequisites:
            if prerequisite not in surface_map:
                blockers.append(
                    f"surface_prerequisite_missing: {surface.surface_id} -> "
                    f"{prerequisite}"
                )
    if _has_cycle(
        {
            surface.surface_id: surface.prerequisites
            for surface in cover.surfaces
            if surface.surface_id in surface_map
        }
    ):
        blockers.append("surface_prerequisite_cycle: dependency graph is cyclic")

    for required_kind in ("fingerprint_corridor", "selected_exemplar"):
        matches = [
            surface
            for surface in cover.surfaces
            if surface.surface_kind == required_kind
        ]
        if len(matches) != 1:
            blockers.append(
                f"production_surface_cardinality_invalid: {required_kind} "
                f"has {len(matches)} entries"
            )

    pass_ids: set[str] = set()
    completed_surfaces: set[str] = set()
    for training_pass in cover.recommended_training_plan.passes:
        if not training_pass.pass_id or training_pass.pass_id in pass_ids:
            blockers.append(f"training_pass_id_invalid: {training_pass.pass_id!r}")
        pass_ids.add(training_pass.pass_id)
        surface = surface_map.get(training_pass.surface_id)
        if surface is None:
            blockers.append(
                f"training_pass_surface_missing: {training_pass.pass_id} -> "
                f"{training_pass.surface_id}"
            )
            continue
        missing = set(surface.prerequisites) - completed_surfaces
        if missing:
            blockers.append(
                f"training_pass_order_invalid: {training_pass.pass_id} precedes "
                f"{sorted(missing)}"
            )
        if not set(surface.required_capabilities).issubset(
            training_pass.required_capabilities
        ):
            blockers.append(
                f"training_pass_capabilities_incomplete: {training_pass.pass_id}"
            )
        completed_surfaces.add(training_pass.surface_id)


def _load_corridor(
    root: Path,
    cover: ProductionTomeCoverPage,
    role_map: dict[str, list[ProductionTomeContentRef]],
    blockers: list[str],
) -> CorridorContract | None:
    surface = _surface(cover, "fingerprint_corridor")
    if surface is None:
        return None
    try:
        summary_payload = _read_role_object(
            root, role_map, "corridor_summary", blockers
        )
        summary = CorridorSummary.from_dict(summary_payload)
        mode_payload = _read_role_object(
            root, role_map, "corridor_mode_table", blockers
        )
        modes_raw = mode_payload["modes"]
        if not isinstance(modes_raw, list):
            raise ValueError("corridor mode table modes must be a list")
        modes = tuple(CorridorMode.from_dict(dict(item)) for item in modes_raw)
        assignments = CorridorAssignmentManifest.from_dict(
            _read_role_object(
                root,
                role_map,
                "corridor_assignment_manifest",
                blockers,
            )
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        blockers.append(f"corridor_contract_invalid: {exc}")
        return None

    if summary_payload.get("schema_version") != "corridor_summary_v3":
        blockers.append("corridor_summary_schema_unsupported")
    if mode_payload.get("schema_version") != "corridor_modes_v2":
        blockers.append("corridor_mode_schema_unsupported")
    if surface.schema_version != "behavioral_surface_v1":
        blockers.append("corridor_surface_schema_unsupported")

    _validate_corridor_summary(summary, modes, assignments, blockers)
    mode_ids = _validate_modes(modes, blockers)
    _validate_assignments(root, role_map, assignments, mode_ids, blockers)
    return CorridorContract(
        surface=surface,
        summary=summary,
        modes=modes,
        assignments=assignments,
    )


def _validate_corridor_summary(
    summary: CorridorSummary,
    modes: tuple[CorridorMode, ...],
    assignments: CorridorAssignmentManifest,
    blockers: list[str],
) -> None:
    expected = {
        "observation_basis": (
            summary.observation_basis,
            "full_token_position_corridor",
        ),
        "degraded": (summary.degraded, False),
        "mode_policy": (summary.mode_policy, "stat_bands_v0"),
        "tracked_stats": (summary.tracked_stats, _TRACKED_STATS),
        "assignment_storage_kind": (
            summary.assignment_storage_kind,
            "packed_numpy_v1",
        ),
        "selected_exemplars_linked": (summary.selected_exemplars_linked, True),
    }
    for field_name, (actual, wanted) in expected.items():
        if actual != wanted:
            blockers.append(
                f"corridor_summary_mismatch: {field_name} must be {wanted!r}, "
                f"got {actual!r}"
            )
    if summary.corridor_stat_top_k < 32:
        blockers.append("corridor_stat_top_k_invalid: must be at least 32")
    if summary.mode_count != len(modes):
        blockers.append("corridor_mode_count_mismatch")
    if summary.assignment_count != assignments.assignment_count:
        blockers.append("corridor_assignment_count_mismatch")
    if assignments.schema_version != "corridor_mode_assignments_v3":
        blockers.append("corridor_assignment_schema_unsupported")
    if assignments.storage_kind != "packed_numpy_v1":
        blockers.append("corridor_assignment_storage_unsupported")
    if assignments.observation_basis != "full_token_position_corridor":
        blockers.append("corridor_assignment_observation_basis_invalid")


def _validate_modes(
    modes: tuple[CorridorMode, ...],
    blockers: list[str],
) -> set[ArtifactLocalModeId]:
    mode_ids: set[ArtifactLocalModeId] = set()
    for mode in modes:
        if mode.mode_id in mode_ids:
            blockers.append(f"corridor_mode_id_duplicate: {mode.mode_id.value!r}")
        mode_ids.add(mode.mode_id)
        if mode.mode_policy != "stat_bands_v0":
            blockers.append(f"corridor_mode_policy_invalid: {mode.mode_id.value!r}")
        if mode.count < 0 or not math.isfinite(mode.share) or mode.share < 0:
            blockers.append(f"corridor_mode_measure_invalid: {mode.mode_id.value!r}")
        if set(mode.bounds) != set(_TRACKED_STATS):
            blockers.append(f"corridor_mode_bounds_incomplete: {mode.mode_id.value!r}")
        for stat, bounds in mode.bounds.items():
            values = (bounds.minimum, bounds.maximum)
            if bounds.mean is not None:
                values += (bounds.mean,)
            if not all(math.isfinite(value) for value in values):
                blockers.append(
                    f"corridor_mode_bounds_nonfinite: {mode.mode_id.value!r}/{stat}"
                )
            if bounds.minimum > bounds.maximum:
                blockers.append(
                    f"corridor_mode_bounds_reversed: {mode.mode_id.value!r}/{stat}"
                )
            if bounds.mean is not None and not (
                bounds.minimum <= bounds.mean <= bounds.maximum
            ):
                blockers.append(
                    f"corridor_mode_mean_outside_bounds: {mode.mode_id.value!r}/{stat}"
                )
    return mode_ids


def _validate_assignments(
    root: Path,
    role_map: dict[str, list[ProductionTomeContentRef]],
    manifest: CorridorAssignmentManifest,
    mode_ids: set[ArtifactLocalModeId],
    blockers: list[str],
) -> None:
    required_arrays = {"position_example_index", "position", "mode_id", "weight"}
    if not required_arrays.issubset(manifest.arrays):
        blockers.append(
            f"corridor_assignment_arrays_missing: "
            f"{sorted(required_arrays - set(manifest.arrays))}"
        )
        return
    arrays: dict[str, np.ndarray] = {}
    for name, descriptor in manifest.arrays.items():
        role = _ARRAY_ROLES.get(name)
        if role is None:
            continue
        ref = _single_ref(role_map, role, blockers)
        if ref is None:
            continue
        if descriptor.path != ref.path:
            blockers.append(f"corridor_assignment_role_path_mismatch: {name}")
        try:
            array = np.load(root / PurePosixPath(ref.path), allow_pickle=False)
        except (OSError, ValueError) as exc:
            blockers.append(f"corridor_assignment_array_invalid: {name}: {exc}")
            continue
        arrays[name] = array
        try:
            expected_dtype = np.dtype(descriptor.dtype)
        except TypeError:
            blockers.append(f"corridor_assignment_dtype_invalid: {name}")
            continue
        if array.dtype != expected_dtype or tuple(array.shape) != descriptor.shape:
            blockers.append(f"corridor_assignment_descriptor_mismatch: {name}")
        if array.ndim != 1 or len(array) != manifest.assignment_count:
            blockers.append(f"corridor_assignment_shape_invalid: {name}")

    metadata_ref = _single_ref(
        role_map,
        "corridor_assignment_examples_metadata",
        blockers,
    )
    if metadata_ref is not None:
        if manifest.examples_metadata_path != metadata_ref.path:
            blockers.append("corridor_examples_metadata_path_mismatch")
        try:
            metadata = _read_jsonl(root / PurePosixPath(metadata_ref.path))
            indexes = [int(item["example_index"]) for item in metadata]
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            blockers.append(f"corridor_examples_metadata_invalid: {exc}")
            metadata = []
            indexes = []
        if len(metadata) != manifest.example_count:
            blockers.append("corridor_examples_metadata_count_mismatch")
        if sorted(indexes) != list(range(manifest.example_count)):
            blockers.append("corridor_examples_metadata_indexes_invalid")

    example_indexes = arrays.get("position_example_index")
    positions = arrays.get("position")
    assigned_modes = arrays.get("mode_id")
    weights = arrays.get("weight")
    if example_indexes is not None:
        if example_indexes.dtype.kind not in "iu" or np.any(example_indexes < 0):
            blockers.append("corridor_example_index_domain_invalid")
        elif np.any(example_indexes >= manifest.example_count):
            blockers.append("corridor_example_index_out_of_range")
    if positions is not None:
        sequence_length = _positive_int_target(role_map, root, "sequence_length")
        if positions.dtype.kind not in "iu" or np.any(positions < 0):
            blockers.append("corridor_position_domain_invalid")
        elif sequence_length is not None and np.any(positions >= sequence_length):
            blockers.append("corridor_position_out_of_range")
    if assigned_modes is not None:
        if assigned_modes.dtype.kind not in "iu":
            blockers.append("corridor_mode_id_array_type_invalid")
        else:
            assigned = {
                ArtifactLocalModeId.from_value(int(value)) for value in assigned_modes
            }
            if not assigned.issubset(mode_ids):
                blockers.append(
                    "corridor_mode_id_domain_invalid: assignment contains an "
                    "unknown artifact-local mode ID"
                )
    if weights is not None and (
        weights.dtype.kind not in "fiu"
        or not np.all(np.isfinite(weights))
        or np.any(weights < 0)
    ):
        blockers.append("corridor_assignment_weight_invalid")


def _load_exemplar(
    root: Path,
    cover: ProductionTomeCoverPage,
    role_map: dict[str, list[ProductionTomeContentRef]],
    corridor: CorridorContract | None,
    blockers: list[str],
) -> ExemplarContract | None:
    surface = _surface(cover, "selected_exemplar")
    if surface is None:
        return None
    try:
        index_payload = _read_role_object(
            root,
            role_map,
            "selected_exemplar_index",
            blockers,
        )
        index_raw = index_payload["selected_exemplars"]
        if not isinstance(index_raw, list):
            raise ValueError("selected exemplar index must contain a list")
        selected_index = tuple(
            SelectedExemplarIndexEntry.from_dict(dict(item)) for item in index_raw
        )
        payloads: list[SelectedExemplarPayload] = []
        for ref in role_map.get("selected_exemplar_payload_shard", []):
            shard = _read_object(root / PurePosixPath(ref.path))
            if shard.get("schema_version") != "selected_exemplar_payload_shard_v1":
                blockers.append("exemplar_payload_schema_unsupported")
            shard_items = shard["selected_exemplars"]
            if not isinstance(shard_items, list):
                raise ValueError("selected exemplar payload shard must contain a list")
            payloads.extend(
                SelectedExemplarPayload.from_dict(dict(item)) for item in shard_items
            )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        blockers.append(f"exemplar_contract_invalid: {exc}")
        return None

    if index_payload.get("schema_version") != "selected_exemplars_v1":
        blockers.append("exemplar_index_schema_unsupported")
    if surface.schema_version != "behavioral_surface_v1":
        blockers.append("exemplar_surface_schema_unsupported")

    payload_tuple = tuple(payloads)
    mode_ids = set() if corridor is None else {mode.mode_id for mode in corridor.modes}
    _validate_exemplars(selected_index, payload_tuple, mode_ids, blockers)
    return ExemplarContract(
        surface=surface,
        selected_index=selected_index,
        payloads=payload_tuple,
        delivery_paths=tuple(
            sorted(
                {entry.delivery_path for entry in selected_index}
                | {payload.index.delivery_path for payload in payload_tuple}
            )
        ),
    )


def _validate_exemplars(
    selected_index: tuple[SelectedExemplarIndexEntry, ...],
    payloads: tuple[SelectedExemplarPayload, ...],
    mode_ids: set[ArtifactLocalModeId],
    blockers: list[str],
) -> None:
    index_map: dict[tuple[str, int], SelectedExemplarIndexEntry] = {}
    for entry in selected_index:
        key = (entry.example_id, entry.selected_position)
        if key in index_map:
            blockers.append(f"exemplar_index_duplicate: {key!r}")
        index_map[key] = entry
        _validate_exemplar_link(entry, mode_ids, blockers)
    payload_map: dict[tuple[str, int], SelectedExemplarPayload] = {}
    for payload in payloads:
        key = (payload.index.example_id, payload.index.selected_position)
        if key in payload_map:
            blockers.append(f"exemplar_payload_duplicate: {key!r}")
        payload_map[key] = payload
        _validate_exemplar_link(payload.index, mode_ids, blockers)
        _validate_exemplar_payload(payload, blockers)
    if set(index_map) != set(payload_map):
        blockers.append("exemplar_index_payload_join_mismatch")
    for key in set(index_map) & set(payload_map):
        index_entry = index_map[key]
        payload_entry = payload_map[key].index
        if index_entry != payload_entry:
            blockers.append(f"exemplar_index_payload_metadata_mismatch: {key!r}")


def _validate_exemplar_link(
    entry: SelectedExemplarIndexEntry,
    mode_ids: set[ArtifactLocalModeId],
    blockers: list[str],
) -> None:
    if entry.linkage_status != "linked":
        blockers.append(f"exemplar_corridor_link_status_invalid: {entry.example_id!r}")
    if entry.corridor_mode_id not in mode_ids:
        blockers.append(
            f"exemplar_corridor_mode_unknown: {entry.corridor_mode_id.value!r}"
        )
    if entry.selected_position < 0 or not math.isfinite(entry.selected_score):
        blockers.append(f"exemplar_index_measure_invalid: {entry.example_id!r}")


def _validate_exemplar_payload(
    payload: SelectedExemplarPayload,
    blockers: list[str],
) -> None:
    key = (payload.index.example_id, payload.index.selected_position)
    widths = {
        len(payload.top_token_ids),
        len(payload.top_log_probs),
        len(payload.top_probs),
        len(payload.selection_mask),
    }
    if len(widths) != 1 or not widths or next(iter(widths)) == 0:
        blockers.append(f"exemplar_payload_width_mismatch: {key!r}")
        return
    width = next(iter(widths))
    if not 1 <= payload.effective_top_k <= width:
        blockers.append(f"exemplar_effective_top_k_invalid: {key!r}")
    if sum(payload.selection_mask) != payload.effective_top_k:
        blockers.append(f"exemplar_selection_mask_invalid: {key!r}")
    if payload.dynamic_top_k.get("effective_top_k") != payload.effective_top_k:
        blockers.append(f"exemplar_dynamic_top_k_mismatch: {key!r}")
    if payload.sequence_length <= payload.index.selected_position:
        blockers.append(f"exemplar_position_out_of_range: {key!r}")
    if payload.vocab_size <= 0 or any(
        token < 0 or token >= payload.vocab_size for token in payload.top_token_ids
    ):
        blockers.append(f"exemplar_token_id_out_of_range: {key!r}")
    numeric = (
        *payload.top_log_probs,
        *payload.top_probs,
        payload.top_mass,
        payload.tail_mass,
        *payload.bucket_masses,
        payload.teacher_entropy,
    )
    if not all(math.isfinite(value) for value in numeric):
        blockers.append(f"exemplar_nonfinite_value: {key!r}")
    if any(value < 0 or value > 1 for value in payload.top_probs):
        blockers.append(f"exemplar_probability_invalid: {key!r}")
    if payload.top_mass < 0 or payload.tail_mass < 0:
        blockers.append(f"exemplar_mass_negative: {key!r}")
    if not math.isclose(
        sum(payload.top_probs), payload.top_mass, rel_tol=1e-5, abs_tol=1e-5
    ):
        blockers.append(f"exemplar_top_mass_mismatch: {key!r}")
    if not math.isclose(
        payload.top_mass + payload.tail_mass,
        1.0,
        rel_tol=1e-5,
        abs_tol=1e-5,
    ):
        blockers.append(f"exemplar_total_mass_invalid: {key!r}")
    if payload.bucket_count != len(payload.bucket_masses) or any(
        value < 0 for value in payload.bucket_masses
    ):
        blockers.append(f"exemplar_bucket_contract_invalid: {key!r}")
    elif not math.isclose(
        sum(payload.bucket_masses),
        payload.tail_mass,
        rel_tol=1e-5,
        abs_tol=1e-5,
    ):
        blockers.append(f"exemplar_bucket_mass_mismatch: {key!r}")


def _surface(
    cover: ProductionTomeCoverPage,
    kind: str,
) -> BehavioralSurfaceContract | None:
    matches = [surface for surface in cover.surfaces if surface.surface_kind == kind]
    return matches[0] if len(matches) == 1 else None


def _single_ref(
    role_map: dict[str, list[ProductionTomeContentRef]],
    role: str,
    blockers: list[str],
) -> ProductionTomeContentRef | None:
    refs = role_map.get(role, [])
    if len(refs) != 1:
        blockers.append(f"content_role_not_singleton: {role} ({len(refs)} entries)")
        return None
    return refs[0]


def _read_role_object(
    root: Path,
    role_map: dict[str, list[ProductionTomeContentRef]],
    role: str,
    blockers: list[str],
) -> dict[str, Any]:
    ref = _single_ref(role_map, role, blockers)
    if ref is None:
        raise ValueError(f"required role {role!r} is unavailable")
    return _read_object(root / PurePosixPath(ref.path))


def _read_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"line {line_number} must contain an object")
        result.append(payload)
    return result


def _is_safe_relative_posix(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and path.as_posix() == value
        and value != "."
    )


def _has_cycle(graph: dict[str, tuple[str, ...]]) -> bool:
    active: set[str] = set()
    complete: set[str] = set()

    def visit(node: str) -> bool:
        if node in active:
            return True
        if node in complete:
            return False
        active.add(node)
        if any(next_node in graph and visit(next_node) for next_node in graph[node]):
            return True
        active.remove(node)
        complete.add(node)
        return False

    return any(visit(node) for node in graph)


def _positive_int_target(
    role_map: dict[str, list[ProductionTomeContentRef]],
    root: Path,
    field_name: str,
) -> int | None:
    refs = role_map.get("target_store_metadata", [])
    if len(refs) != 1:
        return None
    try:
        value = int(_read_object(root / PurePosixPath(refs[0].path))[field_name])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
    return value if value > 0 else None
