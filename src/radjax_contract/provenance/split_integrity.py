from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SplitIntegrityResult:
    ok: bool
    blockers: tuple[str, ...] = ()


def validate_three_way_split(
    *,
    train: list[dict[str, Any]],
    calibration: list[dict[str, Any]],
    final_test: list[dict[str, Any]],
) -> SplitIntegrityResult:
    groups = {
        "train": train,
        "calibration": calibration,
        "final_test": final_test,
    }
    blockers: list[str] = []
    for key in ("example_id", "token_sequence_hash", "source_text_hash"):
        owners: dict[str, str] = {}
        for split_name, records in groups.items():
            for record in records:
                value = record.get(key)
                if value is None:
                    continue
                normalized = str(value)
                previous = owners.get(normalized)
                if previous is not None and previous != split_name:
                    blockers.append(
                        f"{key} overlap between {previous} and {split_name}: "
                        f"{normalized}"
                    )
                owners[normalized] = split_name
    return SplitIntegrityResult(ok=not blockers, blockers=tuple(blockers))
