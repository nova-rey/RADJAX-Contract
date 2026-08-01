"""Portable semantic checks for native-v3 Student corridor resources.

This module deliberately depends only on NumPy and the declared resource
surface.  ``student_consumption`` adapts its findings into the public result;
keeping the checks here prevents the resolver from becoming a second producer
implementation and makes the coordinate contract directly testable.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

_TRACKED_STATS = (
    "entropy",
    "top1_margin",
    "top8_mass",
    "top32_mass",
    "tail_mass",
)
_ASSIGNMENT_ARRAYS = ("position_example_index", "position", "mode_id", "weight")


@dataclass(frozen=True)
class CorridorValidationIssue:
    """A resolver-neutral corridor failure with stable Contract issue code."""

    code: str
    context: dict[str, Any]


def validate_corridor_resources(
    resources: Iterable[Any],
    root: Path,
    *,
    target_lengths: Mapping[int, int] | None = None,
) -> tuple[CorridorValidationIssue, ...]:
    """Validate modes, packed assignments, and every unmasked target coordinate.

    ``resources`` may be resolved-resource dataclasses or mappings with the
    same ``role``, ``resource_id``, ``locator``, ``encoding``, and
    ``consumption`` members.  Target row lengths are derived from declared
    ``target_shard`` resources unless explicitly supplied for callers that
    already decoded them.  The returned tuple is deterministic and contains
    no Tome-specific exception strings.
    """

    rows = list(resources)
    by_role: dict[str, list[Any]] = {}
    for row in rows:
        by_role.setdefault(_value(row, "role"), []).append(row)
    issues: list[CorridorValidationIssue] = []
    modes = _read_modes(_single(by_role, "corridor_mode_table"), root, issues)
    arrays = _read_assignments(_single(by_role, "corridor_assignment"), root, issues)
    observed = _read_observed(
        _single(by_role, "corridor_observed_statistics"), root, issues
    )
    if target_lengths is None:
        target_lengths = _read_target_lengths(
            by_role.get("target_shard", []), root, issues
        )
    if modes is None or arrays is None or observed is None or target_lengths is None:
        return tuple(_ordered(issues))

    example_indexes, positions, mode_ids, weights = arrays
    count = len(example_indexes)
    if any(len(values) != count for values in (positions, mode_ids, weights)):
        issues.append(_issue("TSC040_ASSIGNMENT_COORDINATE", reason="array_length"))
        return tuple(_ordered(issues))
    if any(len(values) != count for values in observed.values()):
        issues.append(_issue("TSC044_MODE_BOUNDS_INVALID", reason="statistic_length"))
        return tuple(_ordered(issues))

    previous: tuple[int, int] | None = None
    seen: set[tuple[int, int]] = set()
    actual: set[tuple[int, int]] = set()
    for index, raw in enumerate(
        zip(example_indexes, positions, mode_ids, weights, strict=True)
    ):
        example, position, mode_id, weight = raw
        if not _integer(example) or not _integer(position) or not _integer(mode_id):
            issues.append(
                _issue("TSC040_ASSIGNMENT_COORDINATE", row=index, reason="integer")
            )
            continue
        coordinate = (int(example), int(position))
        if coordinate in seen:
            issues.append(
                _issue("TSC042_ASSIGNMENT_DUPLICATE", row=index, coordinate=coordinate)
            )
        elif previous is not None and coordinate <= previous:
            issues.append(
                _issue(
                    "TSC040_ASSIGNMENT_COORDINATE",
                    row=index,
                    coordinate=coordinate,
                    reason="not_strictly_sorted",
                )
            )
        seen.add(coordinate)
        actual.add(coordinate)
        previous = coordinate
        length = target_lengths.get(coordinate[0])
        if length is None or coordinate[1] < 0 or coordinate[1] >= length:
            issues.append(
                _issue(
                    "TSC040_ASSIGNMENT_COORDINATE",
                    row=index,
                    coordinate=coordinate,
                    reason="outside_unmasked_target",
                )
            )
        if int(mode_id) not in modes:
            issues.append(
                _issue("TSC043_MODE_UNKNOWN", row=index, mode_id=int(mode_id))
            )
        if not _finite_number(weight) or float(weight) < 0:
            issues.append(_issue("TSC045_WEIGHT_INVALID", row=index))

    expected = {
        (example, position)
        for example, length in target_lengths.items()
        for position in range(length)
    }
    missing = expected - actual
    if missing:
        issues.append(_issue("TSC041_ASSIGNMENT_MISSING", missing_count=len(missing)))

    for stat, values in observed.items():
        for index, value in enumerate(values):
            mode_id = mode_ids[index]
            if not _integer(mode_id) or int(mode_id) not in modes:
                continue
            minimum, maximum = modes[int(mode_id)][stat]
            if not _finite_number(value) or not minimum <= float(value) <= maximum:
                issues.append(
                    _issue(
                        "TSC044_MODE_BOUNDS_INVALID",
                        row=index,
                        mode_id=int(mode_id),
                        statistic=stat,
                    )
                )
    return tuple(_ordered(issues))


def _read_modes(
    resource: Any | None, root: Path, issues: list[CorridorValidationIssue]
) -> dict[int, dict[str, tuple[float, float]]] | None:
    if resource is None:
        return None
    try:
        payload = _json(root / _value(resource, "locator"))
        modes = payload["modes"]
        if not isinstance(modes, list):
            raise ValueError("modes")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        issues.append(
            _issue(
                "TSC030_CONTAINER_ENCODING_MISMATCH", resource_id=_identifier(resource)
            )
        )
        return None
    result: dict[int, dict[str, tuple[float, float]]] = {}
    for index, mode in enumerate(modes):
        try:
            mode_id = mode["mode_id"]
            bounds = mode["bounds"]
            if (
                not _integer(mode_id)
                or int(mode_id) in result
                or set(bounds) != set(_TRACKED_STATS)
            ):
                raise ValueError("mode_id_or_stats")
            normalized: dict[str, tuple[float, float]] = {}
            for stat in _TRACKED_STATS:
                minimum, maximum = (
                    float(bounds[stat]["min"]),
                    float(bounds[stat]["max"]),
                )
                if (
                    not math.isfinite(minimum)
                    or not math.isfinite(maximum)
                    or minimum > maximum
                ):
                    raise ValueError("bounds")
                normalized[stat] = (minimum, maximum)
            result[int(mode_id)] = normalized
        except (KeyError, TypeError, ValueError):
            issues.append(
                _issue(
                    "TSC044_MODE_BOUNDS_INVALID",
                    resource_id=_identifier(resource),
                    mode_row=index,
                )
            )
    return result


def _read_assignments(
    resource: Any | None, root: Path, issues: list[CorridorValidationIssue]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    if resource is None:
        return None
    try:
        with np.load(root / _value(resource, "locator"), allow_pickle=False) as data:
            arrays = tuple(data[name] for name in _ASSIGNMENT_ARRAYS)
    except (KeyError, OSError, ValueError):
        issues.append(
            _issue(
                "TSC030_CONTAINER_ENCODING_MISMATCH", resource_id=_identifier(resource)
            )
        )
        return None
    if any(value.ndim != 1 for value in arrays):
        issues.append(
            _issue("TSC032_RANK_SHAPE_AXIS_MISMATCH", resource_id=_identifier(resource))
        )
        return None
    if (
        any(value.dtype.kind not in "iu" for value in arrays[:3])
        or arrays[3].dtype.kind != "f"
    ):
        issues.append(
            _issue("TSC031_DTYPE_MISMATCH", resource_id=_identifier(resource))
        )
        return None
    return arrays  # type: ignore[return-value]


def _read_observed(
    resource: Any | None, root: Path, issues: list[CorridorValidationIssue]
) -> dict[str, np.ndarray] | None:
    if resource is None:
        return None
    try:
        with np.load(root / _value(resource, "locator"), allow_pickle=False) as data:
            result = {name: data[name] for name in _TRACKED_STATS}
    except (KeyError, OSError, ValueError):
        issues.append(
            _issue(
                "TSC030_CONTAINER_ENCODING_MISMATCH", resource_id=_identifier(resource)
            )
        )
        return None
    if any(value.ndim != 1 or value.dtype.kind != "f" for value in result.values()):
        issues.append(
            _issue("TSC031_DTYPE_MISMATCH", resource_id=_identifier(resource))
        )
        return None
    return result


def _read_target_lengths(
    resources: list[Any], root: Path, issues: list[CorridorValidationIssue]
) -> dict[int, int] | None:
    result: dict[int, int] = {}
    for resource in resources:
        try:
            consumption = _value(resource, "consumption")
            start, end = consumption["row_start"], consumption["row_end"]
            if not _integer(start) or not _integer(end) or start < 0 or end < start:
                raise ValueError("range")
            with np.load(
                root / _value(resource, "locator"), allow_pickle=False
            ) as data:
                lengths = data["corridor_lengths"]
            if (
                lengths.ndim != 1
                or len(lengths) != end - start
                or lengths.dtype.kind not in "iu"
            ):
                raise ValueError("lengths")
            for offset, length in enumerate(lengths):
                if int(length) < 0 or start + offset in result:
                    raise ValueError("overlap")
                result[int(start) + offset] = int(length)
        except (KeyError, OSError, TypeError, ValueError):
            issues.append(
                _issue(
                    "TSC033_SHARD_CARDINALITY_ORDER", resource_id=_identifier(resource)
                )
            )
            return None
    return result


def _single(by_role: Mapping[str, list[Any]], role: str) -> Any | None:
    values = by_role.get(role, [])
    return values[0] if len(values) == 1 else None


def _value(row: Any, key: str) -> Any:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key)


def _identifier(row: Any) -> str:
    return str(_value(row, "resource_id"))


def _json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("object")
    return value


def _integer(value: Any) -> bool:
    return isinstance(value, (int, np.integer)) and not isinstance(value, bool)


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float, np.number))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _issue(code: str, **context: Any) -> CorridorValidationIssue:
    return CorridorValidationIssue(code=code, context=context)


def _ordered(issues: list[CorridorValidationIssue]) -> list[CorridorValidationIssue]:
    return sorted(
        issues,
        key=lambda item: (
            str(item.context.get("resource_id", "")),
            item.code,
            repr(item.context),
        ),
    )
