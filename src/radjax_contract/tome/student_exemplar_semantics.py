"""Portable semantic checks for native-v3 selected-exemplar resources.

This module intentionally accepts decoded records rather than artifact paths.
The Student-consumption resolver owns delivery, integrity, and resource opening;
this helper owns only the cross-record exemplar/passport facts shared by a
producer and an architecture-neutral consumer.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

PROBABILITY_ATOL = 1e-6
PROBABILITY_RTOL = 1e-5
LOG_PROBABILITY_ATOL = 1e-5
LOG_PROBABILITY_RTOL = 1e-5
INACTIVE_PROBABILITY = 0.0
INACTIVE_LOG_PROBABILITY = -100.0


@dataclass(frozen=True)
class ExemplarSemanticFinding:
    """One deterministic semantic failure independent of transport details."""

    code: str
    record_index: int
    context: dict[str, Any]


def validate_exemplar_passport_semantics(
    passports: Sequence[Mapping[str, Any]],
    exemplars: Sequence[Mapping[str, Any]],
    *,
    corridor_coordinates: Collection[tuple[str, int]] | None = None,
    allowed_delivery_paths: Collection[str] = (
        "one_pass_pruned_candidate",
        "two_pass_rerun_selected",
    ),
) -> tuple[ExemplarSemanticFinding, ...]:
    """Validate selected-passport joins and dynamic-top-k payload semantics.

    ``selected_example_id`` plus ``selected_position`` is the authoritative
    passport key.  Exemplar records must occur in strictly increasing,
    contiguous one-based ``rank`` order.  The top-k arrays use a prefix mask;
    inactive probability and log-probability slots are respectively exact
    ``0.0`` and ``-100.0``.  Floating mass checks use Contract-owned constants
    and :func:`math.fsum` in slot order.

    ``corridor_coordinates`` is optional because callers may validate
    exemplars before decoding assignments.  When supplied it makes the
    exemplar-to-corridor join mandatory.
    """

    findings: list[ExemplarSemanticFinding] = []
    passport_by_key: dict[tuple[str, int], Mapping[str, Any]] = {}
    for index, passport in enumerate(passports):
        key = _passport_key(passport)
        if key is None or key in passport_by_key:
            findings.append(_finding("TSC050_PASSPORT_JOIN_INVALID", index))
            continue
        passport_by_key[key] = passport

    expected_rank = 1
    seen_keys: set[tuple[str, int]] = set()
    allowed_paths = frozenset(allowed_delivery_paths)
    for index, exemplar in enumerate(exemplars):
        key = _passport_key(exemplar)
        if key is None or key in seen_keys or key not in passport_by_key:
            findings.append(_finding("TSC050_PASSPORT_JOIN_INVALID", index))
        elif key is not None:
            seen_keys.add(key)
        if exemplar.get("rank") != expected_rank:
            findings.append(
                _finding(
                    "TSC051_EXEMPLAR_RANK_INVALID",
                    index,
                    expected_rank=expected_rank,
                    observed_rank=exemplar.get("rank"),
                )
            )
        expected_rank += 1

        _validate_dynamic_top_k(exemplar, index, findings)
        if (
            key is not None
            and corridor_coordinates is not None
            and key not in corridor_coordinates
        ):
            findings.append(_finding("TSC054_CORRIDOR_LINKAGE_INVALID", index))
        if key is not None and key in passport_by_key:
            _validate_linkage_and_provenance(
                exemplar, passport_by_key[key], index, allowed_paths, findings
            )

    # Every passport must resolve to exactly one exemplar.  Reporting the
    # missing key at a synthetic terminal index retains deterministic ordering
    # without pretending that the source had an exemplar row.
    for key in passport_by_key:
        if key not in seen_keys:
            findings.append(
                _finding(
                    "TSC050_PASSPORT_JOIN_INVALID",
                    len(exemplars),
                    selected_example_id=key[0],
                    selected_position=key[1],
                )
            )
    return tuple(findings)


def _validate_dynamic_top_k(
    record: Mapping[str, Any], index: int, findings: list[ExemplarSemanticFinding]
) -> None:
    names = ("top_token_ids", "top_probs", "top_log_probs", "top_selection_mask")
    values = [record.get(name) for name in names]
    if (
        not all(isinstance(value, list) for value in values)
        or not values[0]
        or len({len(value) for value in values}) != 1
    ):
        findings.append(_finding("TSC052_DYNAMIC_TOPK_INVALID", index))
        return
    tokens, probabilities, log_probabilities, mask = values
    width = len(tokens)
    effective_top_k = record.get("effective_top_k")
    if (
        isinstance(effective_top_k, bool)
        or not isinstance(effective_top_k, int)
        or not 1 <= effective_top_k <= width
        or any(type(value) is not bool for value in mask)
        or mask != [slot < effective_top_k for slot in range(width)]
        or any(
            isinstance(token, bool) or not isinstance(token, int) or token < 0
            for token in tokens
        )
    ):
        findings.append(_finding("TSC052_DYNAMIC_TOPK_INVALID", index))
        return
    if any(not _finite(value) for value in probabilities + log_probabilities):
        findings.append(_finding("TSC053_PROBABILITY_MASS_INVALID", index))
        return
    active_probabilities: list[float] = []
    probability_invalid = False
    for slot, enabled in enumerate(mask):
        probability = float(probabilities[slot])
        log_probability = float(log_probabilities[slot])
        if enabled:
            active_probabilities.append(probability)
            if (
                probability <= 0.0
                or probability > 1.0
                or not _close(
                    log_probability,
                    math.log(probability),
                    LOG_PROBABILITY_ATOL,
                    LOG_PROBABILITY_RTOL,
                )
            ):
                probability_invalid = True
        elif (
            probability != INACTIVE_PROBABILITY
            or log_probability != INACTIVE_LOG_PROBABILITY
        ):
            probability_invalid = True
    top_mass = record.get("top_mass")
    tail_mass = record.get("tail_mass")
    bucket_masses = record.get("bucket_masses", [])
    if (
        not _finite(top_mass)
        or not _finite(tail_mass)
        or not isinstance(bucket_masses, list)
        or any(not _finite(value) for value in bucket_masses)
        or any(float(value) < 0.0 for value in bucket_masses)
        or not _close(
            float(top_mass),
            math.fsum(active_probabilities),
            PROBABILITY_ATOL,
            PROBABILITY_RTOL,
        )
        or not _close(
            float(top_mass) + float(tail_mass), 1.0, PROBABILITY_ATOL, PROBABILITY_RTOL
        )
        or not _close(
            float(tail_mass),
            math.fsum(float(value) for value in bucket_masses),
            PROBABILITY_ATOL,
            PROBABILITY_RTOL,
        )
    ):
        probability_invalid = True
    if probability_invalid:
        findings.append(_finding("TSC053_PROBABILITY_MASS_INVALID", index))


def _validate_linkage_and_provenance(
    exemplar: Mapping[str, Any],
    passport: Mapping[str, Any],
    index: int,
    allowed_paths: frozenset[str],
    findings: list[ExemplarSemanticFinding],
) -> None:
    for field in ("source_shard_id", "source_row", "source_position"):
        if field in passport and exemplar.get(field) != passport.get(field):
            findings.append(
                _finding("TSC054_CORRIDOR_LINKAGE_INVALID", index, field=field)
            )
            break
    exemplar_mode = exemplar.get("corridor_mode_id")
    passport_mode = passport.get("corridor_mode_id")
    if (
        exemplar_mode is not None
        and passport_mode is not None
        and exemplar_mode != passport_mode
    ):
        findings.append(
            _finding("TSC054_CORRIDOR_LINKAGE_INVALID", index, field="corridor_mode_id")
        )
    delivery_path = exemplar.get("source_delivery_path")
    if (
        not isinstance(delivery_path, str)
        or delivery_path not in allowed_paths
        or (
            "source_delivery_path" in passport
            and passport.get("source_delivery_path") != delivery_path
        )
    ):
        findings.append(_finding("TSC055_PROVENANCE_CONTRADICTION", index))


def _passport_key(record: Mapping[str, Any]) -> tuple[str, int] | None:
    example_id = record.get("selected_example_id")
    position = record.get("selected_position")
    if (
        not isinstance(example_id, str)
        or not example_id
        or isinstance(position, bool)
        or not isinstance(position, int)
        or position < 0
    ):
        return None
    return example_id, position


def _finite(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _close(actual: float, expected: float, absolute: float, relative: float) -> bool:
    return math.isclose(actual, expected, abs_tol=absolute, rel_tol=relative)


def _finding(code: str, record_index: int, **context: Any) -> ExemplarSemanticFinding:
    return ExemplarSemanticFinding(code, record_index, context)
