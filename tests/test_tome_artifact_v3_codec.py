"""Focused frozen invariants for the additive Tome artifact v3 codec."""

from __future__ import annotations

import pytest

from radjax_contract.tome.v3.codec import (
    DOMAIN_LABELS,
    FRAME_MAGIC,
    FV3Error,
    canonical_base64_decode,
    canonical_base64_encode,
    digest,
    frame,
    fv3,
    record_sequence_digest,
)
from radjax_contract.tome.v3.strict_json import NumberLexeme, loads


def test_fv3_frame_and_labels_are_final_byte_constants() -> None:
    assert FRAME_MAGIC == bytes.fromhex("524a5446453100")
    assert DOMAIN_LABELS["semantic_root"] == b"radjax.tome.v3.semantic-root.v1"
    assert (
        frame(b"x", b"y") == FRAME_MAGIC + b"\x00\x01x" + (1).to_bytes(8, "big") + b"y"
    )


def test_fv3_map_order_is_byte_order_not_insertion_order() -> None:
    assert fv3({"b": 2, "a": 1}) == fv3({"a": 1, "b": 2})
    assert digest(
        DOMAIN_LABELS["logical_record_id"],
        {"selected_example_id": "x", "selected_position": 1},
    ).startswith("sha256:")


def test_sequence_binds_order_and_closed_record_bytes() -> None:
    first = {"selected_example_id": "a", "selected_position": 1}
    second = {"selected_example_id": "b", "selected_position": 2}
    assert record_sequence_digest([first, second]) != record_sequence_digest(
        [second, first]
    )
    with pytest.raises(FV3Error, match="selection_index_not_contiguous"):
        record_sequence_digest([first], selection_indexes=[1])


def test_strict_json_retains_number_lexemes_and_rejects_duplicate_keys() -> None:
    parsed = loads('{"value":1e0}')
    assert isinstance(parsed["value"], NumberLexeme)
    with pytest.raises(ValueError, match="duplicate_json_key"):
        loads('{"value":1,"value":2}')


def test_base64_requires_canonical_rfc4648_padded_text() -> None:
    encoded = canonical_base64_encode(b"ab")
    assert canonical_base64_decode(encoded) == b"ab"
    with pytest.raises(FV3Error, match="base64_invalid"):
        canonical_base64_decode(encoded.rstrip("="))
