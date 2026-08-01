from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from radjax_contract.tome.student_consumption_corridor import (
    validate_corridor_resources,
)


@dataclass(frozen=True)
class _Resource:
    resource_id: str
    role: str
    locator: str
    consumption: dict[str, object]


def _resources(tmp_path: Path) -> list[_Resource]:
    modes = {
        "modes": [
            {
                "mode_id": 7,
                "bounds": {
                    name: {"min": 0.0, "max": 1.0}
                    for name in (
                        "entropy",
                        "top1_margin",
                        "top8_mass",
                        "top32_mass",
                        "tail_mass",
                    )
                },
            }
        ]
    }
    (tmp_path / "modes.json").write_text(json.dumps(modes), encoding="utf-8")
    np.savez(
        tmp_path / "target.npz",
        corridor_lengths=np.array([2, 1], dtype=np.int32),
    )
    np.savez(
        tmp_path / "assignments.npz",
        position_example_index=np.array([0, 0, 1], dtype=np.int32),
        position=np.array([0, 1, 0], dtype=np.int32),
        mode_id=np.array([7, 7, 7], dtype=np.int32),
        weight=np.array([1.0, 0.0, 1.0], dtype=np.float32),
    )
    np.savez(
        tmp_path / "observed.npz",
        entropy=np.array([0.1, 0.2, 0.3], dtype=np.float32),
        top1_margin=np.array([0.1, 0.2, 0.3], dtype=np.float32),
        top8_mass=np.array([0.1, 0.2, 0.3], dtype=np.float32),
        top32_mass=np.array([0.1, 0.2, 0.3], dtype=np.float32),
        tail_mass=np.array([0.1, 0.2, 0.3], dtype=np.float32),
    )
    return [
        _Resource(
            "target/default",
            "target_shard",
            "target.npz",
            {"row_start": 0, "row_end": 2},
        ),
        _Resource("modes/default", "corridor_mode_table", "modes.json", {}),
        _Resource("assignment/default", "corridor_assignment", "assignments.npz", {}),
        _Resource(
            "observed/default", "corridor_observed_statistics", "observed.npz", {}
        ),
    ]


def _codes(resources: list[_Resource], root: Path) -> list[str]:
    return [item.code for item in validate_corridor_resources(resources, root)]


def test_validates_sorted_complete_unmasked_corridor_coordinates(
    tmp_path: Path,
) -> None:
    assert _codes(_resources(tmp_path), tmp_path) == []


def test_rejects_missing_and_duplicate_assignment_coordinates(tmp_path: Path) -> None:
    resources = _resources(tmp_path)
    np.savez(
        tmp_path / "assignments.npz",
        position_example_index=np.array([0, 0, 0], dtype=np.int32),
        position=np.array([0, 0, 1], dtype=np.int32),
        mode_id=np.array([7, 7, 7], dtype=np.int32),
        weight=np.ones(3, dtype=np.float32),
    )
    codes = _codes(resources, tmp_path)
    assert "TSC041_ASSIGNMENT_MISSING" in codes
    assert "TSC042_ASSIGNMENT_DUPLICATE" in codes


def test_rejects_unsorted_coordinate_unknown_mode_bad_weight_and_bounds(
    tmp_path: Path,
) -> None:
    resources = _resources(tmp_path)
    np.savez(
        tmp_path / "assignments.npz",
        position_example_index=np.array([0, 0, 1], dtype=np.int32),
        position=np.array([1, 0, 0], dtype=np.int32),
        mode_id=np.array([7, 99, 7], dtype=np.int32),
        weight=np.array([1.0, -1.0, 1.0], dtype=np.float32),
    )
    np.savez(
        tmp_path / "observed.npz",
        **{
            name: np.array([0.1, 0.2, 2.0], dtype=np.float32)
            for name in (
                "entropy",
                "top1_margin",
                "top8_mass",
                "top32_mass",
                "tail_mass",
            )
        },
    )
    codes = _codes(resources, tmp_path)
    assert "TSC040_ASSIGNMENT_COORDINATE" in codes
    assert "TSC043_MODE_UNKNOWN" in codes
    assert "TSC045_WEIGHT_INVALID" in codes
    assert "TSC044_MODE_BOUNDS_INVALID" in codes


def test_rejects_duplicate_mode_ids_and_incomplete_bounds(tmp_path: Path) -> None:
    resources = _resources(tmp_path)
    (tmp_path / "modes.json").write_text(
        json.dumps(
            {
                "modes": [
                    {"mode_id": 7, "bounds": {}},
                    {"mode_id": 7, "bounds": {}},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert "TSC044_MODE_BOUNDS_INVALID" in _codes(resources, tmp_path)


def test_rejects_target_range_overlap_or_assignment_outside_unmasked_rows(
    tmp_path: Path,
) -> None:
    resources = _resources(tmp_path)
    resources[0] = _Resource(
        "target/default", "target_shard", "target.npz", {"row_start": 1, "row_end": 3}
    )
    np.savez(
        tmp_path / "assignments.npz",
        position_example_index=np.array([0, 0, 1], dtype=np.int32),
        position=np.array([0, 1, 0], dtype=np.int32),
        mode_id=np.array([7, 7, 7], dtype=np.int32),
        weight=np.ones(3, dtype=np.float32),
    )
    assert "TSC040_ASSIGNMENT_COORDINATE" in _codes(resources, tmp_path)
