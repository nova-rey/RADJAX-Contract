from __future__ import annotations

import pytest

from radjax_contract.tome.m8g import (
    CompactBody,
    JournalState,
    M8GError,
    body_raw_digest,
    compact_from_padded,
    encode_compact_body,
    validate_body_bytes,
    validate_transition,
)


def _body() -> CompactBody:
    return CompactBody(
        profile="student",
        vocab_size=8,
        num_buckets=2,
        top_offsets=(0, 2),
        top_lengths=(2,),
        top_token_ids=(2, 1),
        top_probs=(0.6, 0.2),
        top_log_probs=(-0.5108256, -1.609438),
        effective_top_k=(2,),
        top_mass=(0.8,),
        tail_mass=(0.2,),
        bucket_masses=(0.1, 0.1),
    )


def test_compact_body_round_trip_and_raw_digest() -> None:
    body = _body()
    encoded = encode_compact_body(body)
    assert (
        validate_body_bytes(encoded, profile="student").projection()
        == body.projection()
    )
    assert body_raw_digest(encoded).startswith("sha256:")


def test_padded_projection_copies_only_masked_entries() -> None:
    body = compact_from_padded(
        {
            "vocab_size": 8,
            "num_buckets": 2,
            "top_selection_mask": [[False, True, True, False]],
            "top_token_ids": [[7, 2, 1, 0]],
            "top_probs": [[0.0, 0.6, 0.2, 0.0]],
            "top_log_probs": [[0.0, -0.5108256, -1.609438, 0.0]],
            "effective_top_k": [2],
            "top_mass": [0.8],
            "tail_mass": [0.2],
            "bucket_masses": [[0.1, 0.1]],
        },
        profile="student",
    )
    assert body.top_token_ids == (2, 1)
    assert body.top_lengths == (2,)


def test_invalid_journal_transition_rejected() -> None:
    with pytest.raises(M8GError):
        validate_transition(JournalState.BODY_WRITTEN, JournalState.COMMITTED)


def test_committed_transition_is_idempotent() -> None:
    validate_transition(JournalState.COMMITTED, JournalState.COMMITTED)
