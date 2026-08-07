"""Byte-exact FV3 primitives for the final Tome artifact Contract v3."""

from __future__ import annotations

import base64
import hashlib
import math
import struct
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

FRAME_MAGIC = b"RJTFE1\x00"
DOMAIN_LABELS = {
    "logical_record_id": b"radjax.tome.v3.logical-record-id.v1",
    "semantic_authority": b"radjax.tome.v3.semantic-authority.v1",
    "behavioral_policy": b"radjax.tome.v3.behavioral-policy.v1",
    "record_sequence": b"radjax.tome.v3.record-sequence.v1",
    "semantic_root": b"radjax.tome.v3.semantic-root.v1",
}
PREFIX = "sha256:"
I64_MIN = -(1 << 63)
I64_MAX = (1 << 63) - 1


class FV3Error(ValueError):
    """Raised when a value cannot be represented by FV3."""


def u64(value: int) -> bytes:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value < 1 << 64
    ):
        raise FV3Error("u64_out_of_range")
    return value.to_bytes(8, "big")


def frame(label: bytes, payload: bytes) -> bytes:
    if not isinstance(label, bytes) or len(label) > 0xFFFF:
        raise FV3Error("label_invalid")
    return (
        FRAME_MAGIC
        + len(label).to_bytes(2, "big")
        + label
        + u64(len(payload))
        + payload
    )


def _text(value: str) -> bytes:
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise FV3Error("text_invalid") from exc
    return b"\x20" + u64(len(encoded)) + encoded


def fv3(value: Any) -> bytes:
    """Encode a schema-directed value after its caller has established its type."""

    if value is None:
        return b"\x00"
    if value is False:
        return b"\x01"
    if value is True:
        return b"\x02"
    if isinstance(value, int) and not isinstance(value, bool):
        if not I64_MIN <= value <= I64_MAX:
            raise FV3Error("i64_out_of_range")
        return b"\x10" + value.to_bytes(8, "big", signed=True)
    if isinstance(value, float):
        if not math.isfinite(value) or value == 0.0 and math.copysign(1.0, value) < 0:
            raise FV3Error("binary64_invalid")
        return b"\x11" + struct.pack(">d", value)
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        items = [fv3(item) for item in value]
        return (
            b"\x30"
            + u64(len(items))
            + b"".join(u64(len(item)) + item for item in items)
        )
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise FV3Error("map_key_invalid")
        pairs = []
        for key in sorted(value, key=lambda item: item.encode("utf-8")):
            encoded_key = key.encode("utf-8", "strict")
            encoded_value = fv3(value[key])
            pairs.append(
                u64(len(encoded_key))
                + encoded_key
                + u64(len(encoded_value))
                + encoded_value
            )
        return b"\x40" + u64(len(pairs)) + b"".join(pairs)
    raise FV3Error("value_type_invalid")


def decimal_to_binary64(lexeme: str) -> float:
    """Normalize one retained JSON number lexeme under the v3 binary64 rule."""

    if not isinstance(lexeme, str) or not lexeme or lexeme.startswith("+"):
        raise FV3Error("numeric_lexeme_invalid")
    try:
        with localcontext() as context:
            context.prec = 1100
            decimal = Decimal(lexeme)
    except InvalidOperation as exc:
        raise FV3Error("numeric_lexeme_invalid") from exc
    if not decimal.is_finite() or decimal.is_signed() and decimal.is_zero():
        raise FV3Error("binary64_invalid")
    try:
        result = float(decimal)
    except (OverflowError, ValueError) as exc:
        raise FV3Error("binary64_invalid") from exc
    if not math.isfinite(result):
        raise FV3Error("binary64_invalid")
    return result


def hash_frame(label: bytes, payload: bytes) -> str:
    """Hash one exact FV3 frame and render the Contract digest spelling."""

    return PREFIX + hashlib.sha256(frame(label, payload)).hexdigest()


def digest(label: bytes, value: Any) -> str:
    """Hash a single schema-directed FV3 value under ``label``."""

    return hash_frame(label, fv3(value))


def digest_bytes(value: str) -> bytes:
    if not isinstance(value, str) or not value.startswith(PREFIX) or len(value) != 71:
        raise FV3Error("digest_invalid")
    try:
        decoded = bytes.fromhex(value[len(PREFIX) :])
    except ValueError as exc:
        raise FV3Error("digest_invalid") from exc
    if len(decoded) != 32 or value != PREFIX + decoded.hex():
        raise FV3Error("digest_invalid")
    return decoded


def logical_record_id(record: Mapping[str, Any]) -> str:
    return digest(
        DOMAIN_LABELS["logical_record_id"],
        {
            "selected_example_id": record["selected_example_id"],
            "selected_position": record["selected_position"],
        },
    )


def record_sequence_digest(
    records: Sequence[Mapping[str, Any]],
    *,
    selection_indexes: Sequence[int] | None = None,
) -> str:
    """Return the ordered sequence identity for closed semantic records.

    ``selection_indexes`` is deliberately separate from the record map: it is
    ordering metadata and never becomes a semantic record field.
    """

    if selection_indexes is None:
        selection_indexes = list(range(len(records)))
    if list(selection_indexes) != list(range(len(records))):
        raise FV3Error("selection_index_not_contiguous")
    payload = bytearray(u64(len(records)))
    for selection_index, record in zip(selection_indexes, records, strict=True):
        encoded = fv3(record)
        payload.extend(u64(selection_index))
        payload.extend(digest_bytes(logical_record_id(record)))
        payload.extend(u64(len(encoded)))
        payload.extend(encoded)
    return hash_frame(DOMAIN_LABELS["record_sequence"], bytes(payload))


def semantic_root(identity_without_root: Mapping[str, Any]) -> str:
    """Return the v3 semantic root for the exact closed identity map."""

    return digest(DOMAIN_LABELS["semantic_root"], identity_without_root)


def canonical_base64_encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def canonical_base64_decode(value: str) -> bytes:
    if not isinstance(value, str) or any(char.isspace() for char in value):
        raise FV3Error("base64_invalid")
    try:
        decoded = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise FV3Error("base64_invalid") from exc
    if canonical_base64_encode(decoded) != value:
        raise FV3Error("base64_invalid")
    return decoded
