"""Contract-owned native Tome v3 Student-consumption validation."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

PROFILE_ID = "native_v3_student_v1"
CONSUMPTION_CONTRACT_VERSION = "1.0.0"
_DELIVERY = {"one_pass_pruned_candidate", "two_pass_rerun_selected"}
_TARGET_SOURCE = re.compile(r"^shards/shard-(\d{5})\.npz$")
_EXEMPLAR_SOURCE = re.compile(r"^selected_exemplars/selected-exemplars-(\d{5})\.json$")
_CURRICULUM_SOURCE = re.compile(r"^curriculum/([a-z0-9][a-z0-9_-]*)\.json$")


@dataclass(frozen=True)
class StudentTomeConsumptionResult:
    ok: bool
    errors: tuple[str, ...]
    details: tuple[str, ...]
    profile_id: str
    semantic_digest: str | None = None


def student_consumption_contract_root() -> Path:
    return Path(
        str(
            files("radjax_contract").joinpath(
                "contracts", "radjax_tome", "consumption", "v1"
            )
        )
    )


def student_consumption_profile_path(profile_id: str = PROFILE_ID) -> Path:
    if profile_id != PROFILE_ID:
        raise ValueError("SC001_PROFILE_UNSUPPORTED")
    return student_consumption_contract_root() / "profiles" / f"{profile_id}.json"


def validate_student_tome_consumption(
    tome: str | Path, *, profile_id: str = PROFILE_ID
) -> StudentTomeConsumptionResult:
    """Validate the exact files and semantics needed for Student batches."""

    errors: list[str] = []
    details: list[str] = []
    if profile_id != PROFILE_ID:
        return _done(errors, details, profile_id, "SC001_PROFILE_UNSUPPORTED")
    root = Path(tome)
    try:
        cover = _object(root / "cover_page.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _done(errors, details, profile_id, "SC004_MANIFEST_INVALID", str(exc))
    if cover.get("schema_version") != "radjax_tome_cover_v3":
        return _done(errors, details, profile_id, "SC002_COVER_SCHEMA_UNSUPPORTED")
    package = cover.get("package", {})
    if package.get("profile") not in {"unpacked", "student", "full_debug_provenance"}:
        _add(errors, details, "SC003_PACKAGE_PROFILE_UNSUPPORTED")
    if package.get("transport") not in {"directory", "rtome", "tgz"}:
        _add(errors, details, "SC023_TRANSPORT_UNSUPPORTED")
    identity = cover.get("identity", {})
    payload = identity.get("training_payload")
    raw_inventory = cover.get("manifests", {}).get("content", {}).get("inventory")
    if not isinstance(payload, list) or not isinstance(raw_inventory, list):
        return _done(errors, details, profile_id, "SC004_MANIFEST_INVALID")
    inventory: dict[str, dict[str, Any]] = {}
    for item in raw_inventory:
        path = item.get("path") if isinstance(item, dict) else None
        if not isinstance(path, str) or not _safe(path) or path in inventory:
            _add(errors, details, "SC004_MANIFEST_INVALID", repr(path))
            continue
        inventory[path] = item
        file = root / path
        if not file.is_file():
            _add(errors, details, "SC008_INVENTORY_BINDING_MISSING", path)
        elif (
            item.get("sha256")
            != "sha256:" + hashlib.sha256(file.read_bytes()).hexdigest()
        ):
            _add(errors, details, "SC009_INVENTORY_DIGEST_MISMATCH", path)
    profile = json.loads(student_consumption_profile_path().read_text())
    bindings = {item["logical_id"]: item for item in profile["logical_roles"]}
    required = {key for key, item in bindings.items() if item["required"]}
    observed: dict[str, str] = {}
    for item in payload:
        source_id = item.get("logical_id") if isinstance(item, dict) else None
        if not isinstance(source_id, str):
            _add(errors, details, "SC007_LOGICAL_ID_UNKNOWN", repr(source_id))
            continue
        binding = _binding(source_id, bindings)
        if binding is None:
            _add(errors, details, "SC007_LOGICAL_ID_UNKNOWN", source_id)
            continue
        logical_role, path = binding
        if logical_role in observed:
            _add(errors, details, "SC006_LOGICAL_ID_DUPLICATE", logical_role)
            continue
        observed[logical_role] = path
        if path not in inventory or not inventory[path].get("training_authoritative"):
            _add(errors, details, "SC008_INVENTORY_BINDING_MISSING", logical_role)
    for missing in sorted(required - observed.keys()):
        _add(errors, details, "SC005_LOGICAL_ID_MISSING", missing)
    for family in ("target.shard.", "exemplar.payload."):
        if not any(key.startswith(family) for key in observed):
            _add(errors, details, "SC025_REQUIRED_PAYLOAD_MISSING", family)
    _arrays(root, observed, profile, errors, details)
    _corridor(root, errors, details)
    _exemplars(root, observed, errors, details)
    return StudentTomeConsumptionResult(
        not errors,
        tuple(errors),
        tuple(details),
        profile_id,
        identity.get("semantic_digest"),
    )


def _arrays(
    root: Path,
    observed: dict[str, str],
    profile: dict[str, Any],
    errors: list[str],
    details: list[str],
) -> None:
    for logical_id, path in observed.items():
        if not logical_id.startswith("target.shard."):
            continue
        try:
            with np.load(root / path, allow_pickle=False) as shard:
                base_shape = None
                for spec in profile["target_shard_arrays"]:
                    member = spec["member"]
                    if member not in shard:
                        _add(errors, details, "SC025_REQUIRED_PAYLOAD_MISSING", member)
                        continue
                    value = shard[member]
                    if str(value.dtype) != spec["dtype"]:
                        _add(errors, details, "SC011_DTYPE_INVALID", member)
                    if value.ndim != 2:
                        _add(errors, details, "SC012_SHAPE_INVALID", member)
                    elif base_shape is None:
                        base_shape = value.shape
                    elif value.shape != base_shape:
                        _add(errors, details, "SC013_AXIS_ALIGNMENT_INVALID", member)
                    if member == "attention_mask" and not np.isin(value, (0, 1)).all():
                        _add(errors, details, "SC015_MASK_INVALID")
        except (OSError, ValueError):
            _add(errors, details, "SC010_ENCODING_INVALID", path)
    names = ("example_index", "position", "mode_id", "weight")
    arrays = {}
    for name in names:
        logical_id = f"corridor.assignment.{name}"
        if logical_id in observed:
            try:
                arrays[name] = np.load(root / observed[logical_id], allow_pickle=False)
            except (OSError, ValueError):
                _add(errors, details, "SC010_ENCODING_INVALID", logical_id)
    if arrays and len({value.shape for value in arrays.values()}) != 1:
        _add(errors, details, "SC012_SHAPE_INVALID", "assignment arrays")
    weight = arrays.get("weight")
    if weight is not None and (not np.isfinite(weight).all() or (weight < 0).any()):
        _add(errors, details, "SC016_WEIGHT_INVALID")


def _corridor(root: Path, errors: list[str], details: list[str]) -> None:
    try:
        for mode in _object(root / "corridors/corridor_modes.json")["modes"]:
            for bound in mode["bounds"].values():
                low, high = bound["min"], bound["max"]
                if (
                    not all(
                        isinstance(x, (int, float)) and math.isfinite(x)
                        for x in (low, high)
                    )
                    or low > high
                ):
                    _add(errors, details, "SC018_CORRIDOR_BOUNDS_INVALID")
    except (OSError, ValueError, KeyError, TypeError):
        _add(errors, details, "SC017_CORRIDOR_MODE_INVALID")


def _exemplars(
    root: Path, observed: dict[str, str], errors: list[str], details: list[str]
) -> None:
    try:
        rows = _object(root / "leaderboards/selected_exemplars.json")[
            "selected_exemplars"
        ]
        index = {
            (row["selected_example_id"], row["selected_position"]): row for row in rows
        }
        payloads = []
        for logical_id, path in sorted(observed.items()):
            if logical_id.startswith("exemplar.payload."):
                payloads += _object(root / path)["selected_exemplars"]
        if set(index) != {
            (row["selected_example_id"], row["selected_position"]) for row in payloads
        }:
            _add(errors, details, "SC019_EXEMPLAR_PASSPORT_INVALID")
        for row in payloads:
            key = (row["selected_example_id"], row["selected_position"])
            passport = index.get(key)
            if passport is None or any(
                passport.get(field) != row.get(field)
                for field in (
                    "corridor_mode_id",
                    "selected_policy",
                    "source_delivery_path",
                )
            ):
                _add(errors, details, "SC019_EXEMPLAR_PASSPORT_INVALID", repr(key))
            if row.get("source_delivery_path") not in _DELIVERY:
                _add(errors, details, "SC021_DELIVERY_PROVENANCE_INVALID")
            widths = {
                len(row[name])
                for name in (
                    "top_token_ids",
                    "top_log_probs",
                    "top_probs",
                    "top_selection_mask",
                )
            }
            valid = (
                len(widths) == 1
                and sum(row["top_selection_mask"]) == row["effective_top_k"]
            )
            valid &= math.isclose(row["top_mass"] + row["tail_mass"], 1.0, abs_tol=1e-5)
            valid &= math.isclose(
                sum(row["bucket_masses"]), row["tail_mass"], abs_tol=1e-5
            )
            if not valid:
                _add(errors, details, "SC020_EXEMPLAR_TARGET_INVALID", repr(key))
    except (OSError, ValueError, KeyError, TypeError):
        _add(errors, details, "SC019_EXEMPLAR_PASSPORT_INVALID")


def _binding(
    source_id: str, fixed: dict[str, dict[str, Any]]
) -> tuple[str, str] | None:
    for role, item in fixed.items():
        if item["path"] == source_id:
            return role, source_id
    match = _TARGET_SOURCE.fullmatch(source_id)
    if match is not None:
        return f"target.shard.{match.group(1)}", source_id
    match = _EXEMPLAR_SOURCE.fullmatch(source_id)
    if match is not None:
        return f"exemplar.payload.{match.group(1)}", source_id
    match = _CURRICULUM_SOURCE.fullmatch(source_id)
    if match is not None:
        return f"curriculum.{match.group(1)}", source_id
    return None


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _safe(path: str) -> bool:
    pure = PurePosixPath(path)
    return (
        bool(path)
        and not pure.is_absolute()
        and ".." not in pure.parts
        and str(pure) == path
    )


def _add(errors: list[str], details: list[str], code: str, detail: str = "") -> None:
    if code not in errors:
        errors.append(code)
    if detail:
        details.append(f"{code}: {detail}")


def _done(
    errors: list[str], details: list[str], profile: str, code: str, detail: str = ""
) -> StudentTomeConsumptionResult:
    _add(errors, details, code, detail)
    return StudentTomeConsumptionResult(False, tuple(errors), tuple(details), profile)
