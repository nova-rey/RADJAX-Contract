from __future__ import annotations

from copy import deepcopy

from radjax_contract.tome.student_exemplar_semantics import (
    validate_exemplar_passport_semantics,
)


def _passport(rank: int) -> dict[str, object]:
    position = rank - 1
    return {
        "rank": rank,
        "selected_example_id": f"example-{rank}",
        "selected_position": position,
        "source_shard_id": 0,
        "source_row": position,
        "source_position": position,
        "source_delivery_path": "two_pass_rerun_selected",
        "corridor_mode_id": 3,
    }


def _exemplar(rank: int) -> dict[str, object]:
    record = _passport(rank)
    record.update(
        {
            "top_token_ids": [4, 5, 6],
            "top_probs": [0.6, 0.3, 0.0],
            "top_log_probs": [-0.5108256238, -1.2039728043, -100.0],
            "top_selection_mask": [True, True, False],
            "effective_top_k": 2,
            "top_mass": 0.9,
            "tail_mass": 0.1,
            "bucket_masses": [0.04, 0.06],
        }
    )
    return record


def _codes(
    *, passports: list[dict[str, object]], exemplars: list[dict[str, object]]
) -> set[str]:
    coordinates = {
        (str(row["selected_example_id"]), int(row["selected_position"]))
        for row in passports
    }
    return {
        finding.code
        for finding in validate_exemplar_passport_semantics(
            passports, exemplars, corridor_coordinates=coordinates
        )
    }


def test_valid_exemplar_passport_records_have_no_findings() -> None:
    passports = [_passport(1), _passport(2)]
    assert _codes(passports=passports, exemplars=[_exemplar(1), _exemplar(2)]) == set()


def test_duplicate_passport_key_and_missing_exemplar_are_rejected() -> None:
    passports = [_passport(1), _passport(1)]
    assert "TSC050_PASSPORT_JOIN_INVALID" in _codes(
        passports=passports, exemplars=[_exemplar(1)]
    )


def test_exemplar_rank_must_be_contiguous_and_ordered() -> None:
    first, second = _exemplar(1), _exemplar(2)
    first["rank"] = 2
    assert "TSC051_EXEMPLAR_RANK_INVALID" in _codes(
        passports=[_passport(1), _passport(2)], exemplars=[first, second]
    )


def test_dynamic_top_k_requires_prefix_mask() -> None:
    exemplar = _exemplar(1)
    exemplar["top_selection_mask"] = [True, False, True]
    assert "TSC052_DYNAMIC_TOPK_INVALID" in _codes(
        passports=[_passport(1)], exemplars=[exemplar]
    )


def test_probability_mass_and_padding_are_validated() -> None:
    exemplar = _exemplar(1)
    exemplar["top_probs"] = [0.6, 0.3, 0.2]
    assert "TSC053_PROBABILITY_MASS_INVALID" in _codes(
        passports=[_passport(1)], exemplars=[exemplar]
    )


def test_corridor_and_provenance_links_must_agree() -> None:
    passport = _passport(1)
    exemplar = deepcopy(_exemplar(1))
    exemplar["source_row"] = 7
    exemplar["source_delivery_path"] = "one_pass_full"
    codes = _codes(passports=[passport], exemplars=[exemplar])
    assert "TSC054_CORRIDOR_LINKAGE_INVALID" in codes
    assert "TSC055_PROVENANCE_CONTRADICTION" in codes
