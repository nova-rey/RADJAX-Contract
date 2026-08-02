"""Identity-domain regressions for the additive v6 behavioral contract."""

from __future__ import annotations

import numpy as np
import pytest

from radjax_contract.tome.student_consumption_v6 import (
    canonical_authority_reference_identity,
    canonical_behavioral_authority_digest,
    canonical_composition_digest,
    canonical_multipart_npy_identity,
    canonical_npy_component_identity,
    canonical_selected_passport_identity,
)


def _identity(letter: str) -> str:
    return "sha256:" + letter * 64


def _authority_registry() -> list[dict[str, str]]:
    return [
        {
            "resource_id": "authority_reference/default",
            "role": "authority_reference",
            "schema": "authority-v1",
            "semantic_identity": _identity("a"),
        },
        {
            "resource_id": "corridor_assignment/default",
            "role": "corridor_assignment",
            "schema": "assignment-v1",
            "semantic_identity": _identity("b"),
        },
    ]


def test_npy_component_identity_frames_semantic_metadata_and_values() -> None:
    array = np.array([[1, 2]], dtype=np.int32)
    baseline = canonical_npy_component_identity(
        role="target_shard",
        component="input_ids",
        array=array,
        axes=("example", "sequence_position"),
    )
    assert baseline != canonical_npy_component_identity(
        role="target_shard",
        component="attention_mask",
        array=array,
        axes=("example", "sequence_position"),
    )
    assert baseline != canonical_npy_component_identity(
        role="target_shard",
        component="input_ids",
        array=array.astype(np.int64),
        axes=("example", "sequence_position"),
    )
    assert baseline != canonical_npy_component_identity(
        role="target_shard",
        component="input_ids",
        array=np.array([[1, 3]], dtype=np.int32),
        axes=("example", "sequence_position"),
    )


def test_multipart_identity_is_closed_and_name_ordered() -> None:
    components = [
        {"component": "attention_mask", "semantic_identity": _identity("a")},
        {"component": "input_ids", "semantic_identity": _identity("b")},
    ]
    digest = canonical_multipart_npy_identity(
        role="target_shard", components=components
    )
    assert digest.startswith("sha256:")
    with pytest.raises(ValueError, match="name-sorted"):
        canonical_multipart_npy_identity(
            role="target_shard", components=list(reversed(components))
        )


def test_delivery_registry_changes_composition_not_behavioral_authority() -> None:
    authority = _authority_registry()
    behavioral = canonical_behavioral_authority_digest(
        language_binding_digest=_identity("c"),
        behavioral_source_identity=_identity("d"),
        authority_registry=authority,
        required_joins=("assignment_to_target",),
        selection_authority_digest=_identity("e"),
    )
    first = canonical_composition_digest(
        behavioral_authority_digest=behavioral,
        authority_registry=authority,
        non_authority_registry=[
            {
                "resource_id": "delivery_receipt/default",
                "role": "delivery_receipt",
                "schema": "receipt-v1",
                "semantic_identity": _identity("f"),
            }
        ],
        package_semantic_identity=_identity("1"),
    )
    second = canonical_composition_digest(
        behavioral_authority_digest=behavioral,
        authority_registry=authority,
        non_authority_registry=[
            {
                "resource_id": "delivery_receipt/default",
                "role": "delivery_receipt",
                "schema": "receipt-v1",
                "semantic_identity": _identity("0"),
            }
        ],
        package_semantic_identity=_identity("1"),
    )
    assert first != second


def test_closed_passport_and_authority_projections_reject_extra_fields() -> None:
    passport = {
        "schema_version": "radjax_selected_passport_v6",
        "selected_example_id": "example-0",
        "selected_position": 0,
        "rank": 1,
        "selected_score": 1.0,
        "selected_policy": "fixed",
        "corridor_mode_id": 0,
        "corridor_fingerprint_id": "fingerprint-0",
        "corridor_assignment_status": "selected",
        "selection_integration_config_hash": _identity("a"),
    }
    assert canonical_selected_passport_identity([passport]).startswith("sha256:")
    with pytest.raises(ValueError, match="closed"):
        canonical_selected_passport_identity([{**passport, "source_row": 0}])
    reference = {
        "schema_version": "radjax_behavioral_authority_reference_v6",
        "selection_integration_config_hash": _identity("a"),
        "score_pass_authority_hash": _identity("b"),
        "delivery_authority_hash": _identity("c"),
    }
    assert canonical_authority_reference_identity(reference).startswith("sha256:")
