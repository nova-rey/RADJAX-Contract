from __future__ import annotations

from typing import Any

from radjax_contract.provenance import validate_three_way_split


def validate_split_integrity(
    *,
    train: list[dict[str, Any]],
    calibration: list[dict[str, Any]],
    final_test: list[dict[str, Any]],
) -> object:
    return validate_three_way_split(
        train=train,
        calibration=calibration,
        final_test=final_test,
    )
