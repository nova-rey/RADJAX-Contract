from __future__ import annotations

import hashlib

import pytest

from radjax_contract.tome import m8g
from radjax_contract.tome.m8g import (
    CompactBody,
    JournalState,
    M8GError,
    body_raw_digest,
    compact_from_padded,
    encode_compact_body,
    manifest_semantic_id,
    validate_body_bytes,
    validate_manifest,
    validate_receipt,
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
    decoded = validate_body_bytes(encoded, profile="student")
    assert decoded.top_token_ids == body.top_token_ids
    assert decoded.effective_top_k == body.effective_top_k
    assert decoded.top_probs == pytest.approx(body.top_probs, rel=1e-6)
    assert decoded.top_log_probs == pytest.approx(body.top_log_probs, rel=1e-6)
    assert isinstance(body_raw_digest(encoded), bytes)
    assert len(body_raw_digest(encoded)) == 32
    label = b"RDX-BODY-RAW-1"
    assert (
        body_raw_digest(encoded)
        == hashlib.sha256(len(label).to_bytes(2, "little") + label + encoded).digest()
    )
    with pytest.raises(M8GError):
        validate_body_bytes(encoded[:-1], profile="student")


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


def test_manifest_requires_closed_binding_and_body_identity() -> None:
    body = _body()
    manifest = {
        "schema_version": "selected_exemplar_manifest_v1",
        "profile": "student",
        "selected_example_id": "example-1",
        "selected_position": 2,
        "source_passport_id": "passport-1",
        "corridor_mode_id": None,
        "corridor_fingerprint_id": None,
        "selection_obligation_count": 0,
        "selection_obligations": [],
        "body_semantic_id": body.semantic_id,
        "body_raw_digest": body_raw_digest(encode_compact_body(body)),
        "authority_id": b"\x01" * 32,
        "selection_authority_id": b"\x02" * 32,
        "package_role": "student",
    }
    manifest["manifest_semantic_id"] = manifest_semantic_id(manifest)
    validate_manifest(manifest, body)
    with pytest.raises(M8GError):
        validate_manifest({**manifest, "body_raw_digest": b"\x00" * 32}, body)
    with pytest.raises(M8GError):
        validate_manifest({**manifest, "unexpected": True}, body)


def test_receipt_binds_profile_and_legal_next_state() -> None:
    receipt = {
        "transaction_id": "tx-1",
        "schema_version": "radjax_contract_m8g_v1",
        "profile_code": 1,
        "state": 1,
        "parent_transaction_id": None,
        "body_path": None,
        "manifest_path": None,
        "body_raw_digest": None,
        "body_size_bytes": None,
        "manifest_raw_digest": None,
        "committed_next_state": 2,
        "configuration_identity": b"\x01" * 32,
        "semantic_authority_identity": b"\x02" * 32,
        "receipt_digest": b"",
    }
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    receipt["receipt_digest"] = m8g._digest(b"RDX-RECEIPT-1", m8g._m8g_fv3(unsigned))
    validate_receipt(receipt)
    with pytest.raises(M8GError):
        validate_receipt({**receipt, "committed_next_state": 12})
    with pytest.raises(M8GError):
        validate_receipt({**receipt, "state": int(JournalState.BODY_PROMOTED)})


def test_compact_monolithic_is_closed_and_round_trips() -> None:
    body = CompactBody(
        profile="compact_k_monolithic",
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
    encoded = m8g.encode_compact_monolithic(body)
    decoded = m8g.decode_compact_monolithic(encoded)
    assert decoded.profile == body.profile
    assert decoded.top_token_ids == body.top_token_ids
    assert decoded.top_probs == pytest.approx(body.top_probs)
    assert decoded.top_log_probs == pytest.approx(body.top_log_probs)
    assert m8g.compact_monolithic_semantic_id(body) != body.semantic_id
    with pytest.raises(M8GError):
        m8g.validate_compact_monolithic_projection(
            {**m8g.compact_monolithic_projection(body), "top_probs": [0.6]}
        )
    projection = m8g.compact_monolithic_projection(body)
    with pytest.raises(M8GError):
        m8g.validate_compact_monolithic_projection({**projection, "position_count": 2})
    with pytest.raises(M8GError):
        m8g.validate_compact_monolithic_projection({**projection, "vocab_size": "8"})
    with pytest.raises(M8GError):
        m8g.validate_compact_monolithic_projection({**projection, "num_buckets": True})
    with pytest.raises(M8GError):
        m8g.validate_compact_monolithic_projection({**projection, "unknown": 1})


def test_compact_monolithic_rejects_integer_float_fields() -> None:
    with pytest.raises(M8GError):
        CompactBody(
            profile="compact_k_monolithic",
            vocab_size=8,
            num_buckets=2,
            top_offsets=(0, 1),
            top_lengths=(1,),
            top_token_ids=(2,),
            top_probs=(1,),
            top_log_probs=(-1.0,),
            effective_top_k=(1,),
            top_mass=(1.0,),
            tail_mass=(0.0,),
            bucket_masses=(0.0, 0.0),
        )
