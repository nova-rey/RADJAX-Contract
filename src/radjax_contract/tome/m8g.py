"""Opt-in M8G compact-body and immutable-body Contract primitives.

This module is deliberately additive: legacy v1-v3 padded records remain
validated by their existing modules.  M8G resources are closed, explicit
flavors and never inferred from a producer command or pathname.
"""

from __future__ import annotations

import hashlib
import math
import struct
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from radjax_contract.tome.v3.codec import fv3

COMPACT_SCHEMA = "selected_exemplar_payload_compact_v1"
COMPACT_MONOLITHIC_SCHEMA = "selected_exemplar_compact_monolithic_v1"
BODY_SCHEMA = "selected_exemplar_body_v1"
MANIFEST_SCHEMA = "selected_exemplar_manifest_v1"
_MANIFEST_FIELDS = {
    "schema_version",
    "profile",
    "selected_example_id",
    "selected_position",
    "source_passport_id",
    "corridor_mode_id",
    "corridor_fingerprint_id",
    "selection_obligation_count",
    "selection_obligations",
    "body_semantic_id",
    "body_raw_digest",
    "authority_id",
    "selection_authority_id",
    "package_role",
}
M8G_VERSION = "radjax_contract_m8g_v1"
PROFILE_CODES = {
    1: "student",
    2: "full_debug",
    3: "producer_evidence",
    4: "compact_k_monolithic",
}
PROFILE_NAMES = {value: key for key, value in PROFILE_CODES.items()}
MAGIC = b"RDXC"


class M8GError(ValueError):
    """Raised when an M8G resource violates its closed contract."""


class JournalState(IntEnum):
    BODY_GENERATING = 1
    BODY_WRITTEN = 2
    BODY_VALIDATED = 3
    BODY_DIGESTED = 4
    BODY_PROMOTED = 5
    MANIFEST_PROVISIONAL = 6
    LINKAGE_FINALIZED = 7
    MANIFEST_VALIDATED = 8
    MANIFEST_PROMOTED = 9
    INVENTORY_COMMITTED = 10
    PACKAGE_VALIDATED = 11
    COMMITTED = 12


_NEXT = {
    state: JournalState(state + 1)
    for state in JournalState
    if state < JournalState.COMMITTED
}


def validate_receipt(receipt: Mapping[str, Any]) -> None:
    """Validate the closed evidence required for one journal transition."""

    fields = {
        "transaction_id",
        "schema_version",
        "profile_code",
        "state",
        "parent_transaction_id",
        "body_path",
        "manifest_path",
        "body_raw_digest",
        "body_size_bytes",
        "manifest_raw_digest",
        "committed_next_state",
        "configuration_identity",
        "semantic_authority_identity",
        "receipt_digest",
    }
    if set(receipt) != fields:
        raise M8GError("receipt_fields_invalid")
    if (
        receipt["schema_version"] != M8G_VERSION
        or receipt["profile_code"] not in PROFILE_CODES
    ):
        raise M8GError("receipt_profile_invalid")
    for key in ("body_raw_digest", "manifest_raw_digest"):
        value = receipt[key]
        if value is not None and (not isinstance(value, bytes) or len(value) != 32):
            raise M8GError("receipt_digest_field_invalid")
    if receipt["body_size_bytes"] is not None and (
        not isinstance(receipt["body_size_bytes"], int)
        or isinstance(receipt["body_size_bytes"], bool)
        or receipt["body_size_bytes"] < 0
    ):
        raise M8GError("receipt_size_invalid")
    for key in ("parent_transaction_id", "body_path", "manifest_path"):
        value = receipt[key]
        if value is not None and (
            not isinstance(value, str) or not value or ".." in value.split("/")
        ):
            raise M8GError("receipt_path_invalid")
    try:
        state = JournalState(receipt["state"])
        proposed = receipt["committed_next_state"]
        if proposed is not None:
            validate_transition(state, JournalState(proposed))
    except (TypeError, ValueError) as exc:
        raise M8GError("receipt_state_invalid") from exc
    if state >= JournalState.BODY_PROMOTED and (
        receipt["body_path"] is None
        or receipt["body_raw_digest"] is None
        or receipt["body_size_bytes"] is None
    ):
        raise M8GError("receipt_body_evidence_missing")
    if state >= JournalState.MANIFEST_PROMOTED and (
        receipt["manifest_path"] is None or receipt["manifest_raw_digest"] is None
    ):
        raise M8GError("receipt_manifest_evidence_missing")
    if not isinstance(receipt["transaction_id"], str) or not receipt["transaction_id"]:
        raise M8GError("receipt_identity_invalid")
    for key in (
        "configuration_identity",
        "semantic_authority_identity",
        "receipt_digest",
    ):
        if not isinstance(receipt[key], bytes) or len(receipt[key]) != 32:
            raise M8GError("receipt_identity_invalid")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    if receipt["receipt_digest"] != _digest(b"RDX-RECEIPT-1", _m8g_fv3(unsigned)):
        raise M8GError("receipt_digest_invalid")


def _domain(label: bytes, payload: bytes) -> bytes:
    return len(label).to_bytes(2, "little") + label + payload


def _digest(label: bytes, payload: bytes) -> bytes:
    return hashlib.sha256(_domain(label, payload)).digest()


def _raw_digest(payload: bytes) -> bytes:
    return hashlib.sha256(_domain(b"RDX-BODY-RAW-1", payload)).digest()


def _m8g_fv3(value: Any) -> bytes:
    """M8G FV3 subset with governed binary32 float fields."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise M8GError("binary32_invalid")
        return b"\x12" + struct.pack(">f", value)
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return b"\x21" + len(raw).to_bytes(8, "big") + raw
    if isinstance(value, Mapping):
        pairs = []
        for key in sorted(value, key=lambda item: item.encode("utf-8")):
            key_bytes = key.encode("utf-8")
            encoded = _m8g_fv3(value[key])
            pairs.append(
                len(key_bytes).to_bytes(8, "big")
                + key_bytes
                + len(encoded).to_bytes(8, "big")
                + encoded
            )
        return b"\x40" + len(pairs).to_bytes(8, "big") + b"".join(pairs)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        encoded = [_m8g_fv3(item) for item in value]
        return (
            b"\x30"
            + len(encoded).to_bytes(8, "big")
            + b"".join(len(item).to_bytes(8, "big") + item for item in encoded)
        )
    return fv3(value)


def _finite(values: Sequence[float], field: str) -> None:
    if any(
        type(value) is not float or not math.isfinite(float(value)) for value in values
    ):
        raise M8GError(f"{field}_non_finite")


def _ints(values: Sequence[int], field: str) -> tuple[int, ...]:
    result = tuple(values)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in result):
        raise M8GError(f"{field}_not_integer")
    return result


@dataclass(frozen=True)
class CompactBody:
    """Closed flattened active-entry representation for selected positions."""

    profile: str
    vocab_size: int
    num_buckets: int
    top_offsets: tuple[int, ...]
    top_lengths: tuple[int, ...]
    top_token_ids: tuple[int, ...]
    top_probs: tuple[float, ...]
    top_log_probs: tuple[float, ...]
    effective_top_k: tuple[int, ...]
    top_mass: tuple[float, ...]
    tail_mass: tuple[float, ...]
    bucket_masses: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.profile not in PROFILE_NAMES:
            raise M8GError("profile_unsupported")
        if self.vocab_size < 1 or self.num_buckets < 1:
            raise M8GError("shape_invalid")
        offsets = _ints(self.top_offsets, "top_offsets")
        lengths = _ints(self.top_lengths, "top_lengths")
        ids = _ints(self.top_token_ids, "top_token_ids")
        effective = _ints(self.effective_top_k, "effective_top_k")
        position_count = len(lengths)
        if len(offsets) != position_count + 1 or len(effective) != position_count:
            raise M8GError("position_array_length_mismatch")
        if offsets[0] != 0 or any(
            offsets[index] > offsets[index + 1] for index in range(len(offsets) - 1)
        ):
            raise M8GError("offsets_invalid")
        if (
            offsets[-1] != len(ids)
            or offsets[-1] != len(self.top_probs)
            or offsets[-1] != len(self.top_log_probs)
        ):
            raise M8GError("active_array_length_mismatch")
        if any(
            lengths[index] != offsets[index + 1] - offsets[index]
            or lengths[index] != effective[index]
            for index in range(position_count)
        ):
            raise M8GError("logical_k_mismatch")
        if any(token < 0 or token >= self.vocab_size for token in ids):
            raise M8GError("token_id_out_of_range")
        if (
            len(self.top_mass) != position_count
            or len(self.tail_mass) != position_count
        ):
            raise M8GError("mass_length_mismatch")
        if len(self.bucket_masses) != position_count * self.num_buckets:
            raise M8GError("bucket_length_mismatch")
        _finite(self.top_probs, "top_probs")
        _finite(self.top_log_probs, "top_log_probs")
        _finite(self.top_mass, "top_mass")
        _finite(self.tail_mass, "tail_mass")
        _finite(self.bucket_masses, "bucket_masses")
        if any(k < 1 or k > self.vocab_size for k in effective):
            raise M8GError("effective_k_invalid")
        for index in range(position_count):
            start, end = offsets[index], offsets[index + 1]
            probs = self.top_probs[start:end]
            if any(probs[index] < probs[index + 1] for index in range(len(probs) - 1)):
                raise M8GError("token_order_invalid")
            # top_mass and tail_mass are the governed CSL mass summaries.
            # Individual binary32 top probabilities may be independently
            # quantized, so their sum is not a second authority value.
            if not math.isclose(
                self.top_mass[index] + self.tail_mass[index],
                1.0,
                rel_tol=2e-5,
                abs_tol=2e-5,
            ):
                raise M8GError("mass_inconsistent")

    @property
    def position_count(self) -> int:
        return len(self.top_lengths)

    def projection(self) -> dict[str, Any]:
        return {
            "schema_version": COMPACT_SCHEMA,
            "profile": self.profile,
            "record_count": 1,
            "position_count": self.position_count,
            "vocab_size": self.vocab_size,
            "num_buckets": self.num_buckets,
            "top_offsets": list(self.top_offsets),
            "top_lengths": list(self.top_lengths),
            "top_token_ids": list(self.top_token_ids),
            "top_probs": list(self.top_probs),
            "top_log_probs": list(self.top_log_probs),
            "effective_top_k": list(self.effective_top_k),
            "top_mass": list(self.top_mass),
            "tail_mass": list(self.tail_mass),
            "bucket_masses": list(self.bucket_masses),
        }

    @property
    def semantic_id(self) -> bytes:
        return _digest(b"RDX-BODY-SEM-1", _m8g_fv3(self.projection()))


def compact_monolithic_projection(body: CompactBody) -> dict[str, Any]:
    """Return the closed monolithic compact package record.

    The body fields remain the governed compact representation; this wrapper
    adds an explicit package flavor so consumers cannot confuse it with a
    split immutable body or a legacy padded payload.
    """

    projection = body.projection()
    projection["schema_version"] = COMPACT_MONOLITHIC_SCHEMA
    projection["storage_flavor"] = "compact_k_monolithic"
    return projection


def compact_monolithic_semantic_id(body: CompactBody) -> bytes:
    return _digest(
        b"RDX-COMPACT-MONO-SEM-1",
        _m8g_fv3(compact_monolithic_projection(body)),
    )


def validate_compact_monolithic_projection(
    projection: Mapping[str, Any], *, profile: str = "compact_k_monolithic"
) -> CompactBody:
    expected = {
        "schema_version",
        "storage_flavor",
        "profile",
        "record_count",
        "position_count",
        "vocab_size",
        "num_buckets",
        "top_offsets",
        "top_lengths",
        "top_token_ids",
        "top_probs",
        "top_log_probs",
        "effective_top_k",
        "top_mass",
        "tail_mass",
        "bucket_masses",
    }
    if set(projection) != expected:
        raise M8GError("compact_monolithic_fields_invalid")
    if (
        projection["schema_version"] != COMPACT_MONOLITHIC_SCHEMA
        or projection["storage_flavor"] != "compact_k_monolithic"
        or projection["profile"] != profile
        or type(projection["record_count"]) is not int
        or projection["record_count"] != 1
        or type(projection["position_count"]) is not int
        or type(projection["vocab_size"]) is not int
        or type(projection["num_buckets"]) is not int
        or projection["position_count"] != len(projection["top_lengths"])
    ):
        raise M8GError("compact_monolithic_flavor_invalid")
    body = CompactBody(
        profile=profile,
        vocab_size=int(projection["vocab_size"]),
        num_buckets=int(projection["num_buckets"]),
        top_offsets=tuple(projection["top_offsets"]),
        top_lengths=tuple(projection["top_lengths"]),
        top_token_ids=tuple(projection["top_token_ids"]),
        top_probs=tuple(projection["top_probs"]),
        top_log_probs=tuple(projection["top_log_probs"]),
        effective_top_k=tuple(projection["effective_top_k"]),
        top_mass=tuple(projection["top_mass"]),
        tail_mass=tuple(projection["tail_mass"]),
        bucket_masses=tuple(projection["bucket_masses"]),
    )
    return body


def encode_compact_monolithic(body: CompactBody) -> bytes:
    return _m8g_fv3(compact_monolithic_projection(body))


def decode_compact_monolithic(
    payload: bytes, *, profile: str = "compact_k_monolithic"
) -> CompactBody:
    value, offset = _decode_fv3(payload, 0)
    if offset != len(payload) or not isinstance(value, Mapping):
        raise M8GError("compact_monolithic_payload_invalid")
    return validate_compact_monolithic_projection(value, profile=profile)


def compact_from_padded(padded: Mapping[str, Any], *, profile: str) -> CompactBody:
    """Project one padded record without changing active ordering or values."""

    mask = padded.get("top_selection_mask")
    ids = padded.get("top_token_ids")
    probs = padded.get("top_probs")
    logs = padded.get("top_log_probs")
    if not all(isinstance(value, Sequence) for value in (mask, ids, probs, logs)):
        raise M8GError("padded_fields_missing")
    if not all(
        len(rows) == len(mask)
        for rows in (
            ids,
            probs,
            logs,
            padded.get("effective_top_k", ()),
            padded.get("top_mass", ()),
            padded.get("tail_mass", ()),
            padded.get("bucket_masses", ()),
        )
    ):
        raise M8GError("padded_row_count_mismatch")
    widths = {len(row) for row in (mask, ids, probs, logs)}
    if len(widths) != 1 or any(
        not isinstance(bit, bool) for row in mask for bit in row
    ):
        raise M8GError("padded_shape_invalid")
    offsets = [0]
    lengths: list[int] = []
    compact_ids: list[int] = []
    compact_probs: list[float] = []
    compact_logs: list[float] = []
    for mask_row, id_row, prob_row, log_row in zip(mask, ids, probs, logs, strict=True):
        active = [index for index, bit in enumerate(mask_row) if bool(bit)]
        if len(active) != int(padded["effective_top_k"][len(lengths)]):
            raise M8GError("padded_active_count_mismatch")
        compact_ids.extend(int(id_row[index]) for index in active)
        compact_probs.extend(float(prob_row[index]) for index in active)
        compact_logs.extend(float(log_row[index]) for index in active)
        lengths.append(len(active))
        offsets.append(offsets[-1] + len(active))
    vocab_size = int(padded["vocab_size"])
    num_buckets = int(padded["num_buckets"])
    buckets = padded["bucket_masses"]
    flat_buckets = tuple(float(value) for row in buckets for value in row)
    return CompactBody(
        profile=profile,
        vocab_size=vocab_size,
        num_buckets=num_buckets,
        top_offsets=tuple(offsets),
        top_lengths=tuple(lengths),
        top_token_ids=tuple(compact_ids),
        top_probs=tuple(compact_probs),
        top_log_probs=tuple(compact_logs),
        effective_top_k=tuple(int(value) for value in padded["effective_top_k"]),
        top_mass=tuple(float(value) for value in padded["top_mass"]),
        tail_mass=tuple(float(value) for value in padded["tail_mass"]),
        bucket_masses=flat_buckets,
    )


def encode_compact_body(body: CompactBody) -> bytes:
    """Encode a deterministic opt-in body resource with explicit shape header."""

    payload = _m8g_fv3(body.projection())
    prefix = struct.pack(
        "<4sHHIIIIQQ",
        MAGIC,
        1,
        PROFILE_NAMES[body.profile],
        1,
        body.position_count,
        body.vocab_size,
        body.num_buckets,
        len(payload),
        0,
    )
    header_crc = zlib.crc32(prefix) & 0xFFFFFFFF
    payload_crc = zlib.crc32(payload) & 0xFFFFFFFF
    return prefix + struct.pack("<II", header_crc, payload_crc) + payload


def encode_compact_body_packed(body: CompactBody) -> bytes:
    """Encode a deterministic packed-array body for new canonical storage."""
    payload = bytearray()
    payload.extend(struct.pack("<IIII", body.position_count, body.vocab_size, body.num_buckets, len(body.top_token_ids)))
    payload.extend(struct.pack(f"<{len(body.top_offsets)}I", *body.top_offsets))
    payload.extend(struct.pack(f"<{len(body.top_lengths)}I", *body.top_lengths))
    payload.extend(struct.pack(f"<{len(body.effective_top_k)}I", *body.effective_top_k))
    payload.extend(struct.pack(f"<{len(body.top_token_ids)}I", *body.top_token_ids))
    for values in (body.top_probs, body.top_log_probs, body.top_mass, body.tail_mass, body.bucket_masses):
        payload.extend(struct.pack(f"<{len(values)}f", *values))
    prefix = struct.pack("<4sHHIIIIQQ", MAGIC, 2, PROFILE_NAMES[body.profile], 1,
                         body.position_count, body.vocab_size, body.num_buckets, len(payload), 0)
    return prefix + struct.pack("<II", zlib.crc32(prefix) & 0xFFFFFFFF, zlib.crc32(payload) & 0xFFFFFFFF) + payload


def validate_packed_body_bytes(body_bytes: bytes, *, profile: str) -> CompactBody:
    """Decode and validate the version-2 packed-array body."""
    if len(body_bytes) < 48 or not body_bytes.startswith(MAGIC):
        raise M8GError("body_truncated_or_magic_invalid")
    _, version, profile_code, _, positions, vocab, buckets, payload_size, manifest = struct.unpack("<4sHHIIIIQQ", body_bytes[:40])
    if version != 2 or PROFILE_CODES.get(profile_code) != profile or manifest != 0:
        raise M8GError("packed_body_header_invalid")
    prefix, payload = body_bytes[:40], body_bytes[48:]
    header_crc, payload_crc = struct.unpack("<II", body_bytes[40:48])
    if len(payload) != payload_size or zlib.crc32(prefix) & 0xFFFFFFFF != header_crc or zlib.crc32(payload) & 0xFFFFFFFF != payload_crc:
        raise M8GError("packed_body_crc_invalid")
    offset = 0
    def take(fmt: str):
        nonlocal offset
        size = struct.calcsize(fmt)
        if offset + size > len(payload):
            raise M8GError("packed_body_truncated")
        value = struct.unpack_from(fmt, payload, offset); offset += size
        return value
    _, _, _, active = take("<IIII")
    offsets = take(f"<{positions + 1}I")
    lengths = take(f"<{positions}I")
    effective = take(f"<{positions}I")
    ids = take(f"<{active}I")
    def floats(count: int): return take(f"<{count}f")
    probs, logs = floats(active), floats(active)
    top_mass, tail_mass = floats(positions), floats(positions)
    bucket_masses = floats(positions * buckets)
    if offset != len(payload):
        raise M8GError("packed_body_trailing_bytes")
    return CompactBody(profile=profile, vocab_size=vocab, num_buckets=buckets,
                       top_offsets=offsets, top_lengths=lengths, top_token_ids=ids,
                       top_probs=probs, top_log_probs=logs, effective_top_k=effective,
                       top_mass=top_mass, tail_mass=tail_mass, bucket_masses=bucket_masses)


def body_raw_digest(body_bytes: bytes) -> bytes:
    if len(body_bytes) < 48 or not body_bytes.startswith(MAGIC):
        raise M8GError("body_magic_invalid")
    prefix = body_bytes[:40]
    _, version, _, _, _, _, _, payload_size, manifest_bytes = struct.unpack(
        "<4sHHIIIIQQ", body_bytes[:40]
    )
    header_crc, payload_crc = struct.unpack("<II", body_bytes[40:48])
    payload = body_bytes[48:]
    if (
        version not in (1, 2)
        or manifest_bytes != 0
        or len(body_bytes) != 48 + payload_size
        or zlib.crc32(prefix) & 0xFFFFFFFF != header_crc
        or zlib.crc32(payload) & 0xFFFFFFFF != payload_crc
    ):
        raise M8GError("body_framing_invalid")
    return _raw_digest(body_bytes)


def validate_body_bytes(body_bytes: bytes, *, profile: str) -> CompactBody:
    if len(body_bytes) < 48 or not body_bytes.startswith(MAGIC):
        raise M8GError("body_truncated_or_magic_invalid")
    (
        _,
        version,
        profile_code,
        record_count,
        position_count,
        vocab_size,
        num_buckets,
        payload_size,
        manifest_bytes,
    ) = struct.unpack("<4sHHIIIIQQ", body_bytes[:40])
    if version != 1 or PROFILE_CODES.get(profile_code) != profile:
        raise M8GError("body_profile_invalid")
    prefix = body_bytes[:40]
    header_crc, payload_crc = struct.unpack("<II", body_bytes[40:48])
    payload = body_bytes[48:]
    if (
        len(payload) != payload_size
        or manifest_bytes != 0
        or zlib.crc32(prefix) & 0xFFFFFFFF != header_crc
        or zlib.crc32(payload) & 0xFFFFFFFF != payload_crc
    ):
        raise M8GError("body_payload_size_mismatch")
    value, offset = _decode_fv3(payload, 0)
    if offset != len(payload) or not isinstance(value, Mapping):
        raise M8GError("body_projection_invalid")
    if any(
        (
            value.get("record_count") != record_count,
            value.get("position_count") != position_count,
            value.get("vocab_size") != vocab_size,
            value.get("num_buckets") != num_buckets,
            value.get("schema_version") != COMPACT_SCHEMA,
            value.get("profile") != profile,
        )
    ):
        raise M8GError("body_header_projection_mismatch")
    try:
        body = CompactBody(
            profile=str(value["profile"]),
            vocab_size=int(value["vocab_size"]),
            num_buckets=int(value["num_buckets"]),
            top_offsets=tuple(value["top_offsets"]),
            top_lengths=tuple(value["top_lengths"]),
            top_token_ids=tuple(value["top_token_ids"]),
            top_probs=tuple(value["top_probs"]),
            top_log_probs=tuple(value["top_log_probs"]),
            effective_top_k=tuple(value["effective_top_k"]),
            top_mass=tuple(value["top_mass"]),
            tail_mass=tuple(value["tail_mass"]),
            bucket_masses=tuple(value["bucket_masses"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise M8GError("body_projection_invalid") from exc
    return body


def _decode_fv3(value: bytes, offset: int) -> tuple[Any, int]:
    if offset >= len(value):
        raise M8GError("fv3_truncated")
    tag = value[offset]
    offset += 1
    if tag == 0:
        return None, offset
    if tag == 1:
        return False, offset
    if tag == 2:
        return True, offset
    if tag == 0x10:
        if offset + 8 > len(value):
            raise M8GError("fv3_truncated")
        return int.from_bytes(
            value[offset : offset + 8], "big", signed=True
        ), offset + 8
    if tag == 0x11:
        if offset + 8 > len(value):
            raise M8GError("fv3_truncated")
        return struct.unpack(">d", value[offset : offset + 8])[0], offset + 8
    if tag == 0x12:
        if offset + 4 > len(value):
            raise M8GError("fv3_truncated")
        return struct.unpack(">f", value[offset : offset + 4])[0], offset + 4
    if tag == 0x20:
        if offset + 8 > len(value):
            raise M8GError("fv3_truncated")
        size = int.from_bytes(value[offset : offset + 8], "big")
        offset += 8
        if offset + size > len(value):
            raise M8GError("fv3_truncated")
        return value[offset : offset + size].decode("utf-8"), offset + size
    if tag == 0x21:
        if offset + 8 > len(value):
            raise M8GError("fv3_truncated")
        size = int.from_bytes(value[offset : offset + 8], "big")
        offset += 8
        if offset + size > len(value):
            raise M8GError("fv3_truncated")
        return value[offset : offset + size], offset + size
    if tag in (0x30, 0x40):
        if offset + 8 > len(value):
            raise M8GError("fv3_truncated")
        count = int.from_bytes(value[offset : offset + 8], "big")
        offset += 8
        if tag == 0x30:
            items = []
            for _ in range(count):
                if offset + 8 > len(value):
                    raise M8GError("fv3_truncated")
                size = int.from_bytes(value[offset : offset + 8], "big")
                offset += 8
                item, end = _decode_fv3(value[offset : offset + size], 0)
                if end != size:
                    raise M8GError("fv3_item_invalid")
                items.append(item)
                offset += size
            return items, offset
        result: dict[str, Any] = {}
        for _ in range(count):
            if offset + 8 > len(value):
                raise M8GError("fv3_truncated")
            key_size = int.from_bytes(value[offset : offset + 8], "big")
            offset += 8
            key = value[offset : offset + key_size].decode("utf-8")
            offset += key_size
            if key in result:
                raise M8GError("fv3_duplicate_map_key")
            if offset + 8 > len(value):
                raise M8GError("fv3_truncated")
            item_size = int.from_bytes(value[offset : offset + 8], "big")
            offset += 8
            item, end = _decode_fv3(value[offset : offset + item_size], 0)
            if end != item_size:
                raise M8GError("fv3_item_invalid")
            result[key] = item
            offset += item_size
        return result, offset
    raise M8GError("fv3_tag_invalid")


def manifest_semantic_id(manifest: Mapping[str, Any]) -> bytes:
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise M8GError("manifest_schema_invalid")
    if set(manifest) != _MANIFEST_FIELDS and set(manifest) != (
        _MANIFEST_FIELDS | {"manifest_semantic_id"}
    ):
        raise M8GError("manifest_fields_invalid")
    if "manifest_semantic_id" in manifest:
        manifest = {
            key: value
            for key, value in manifest.items()
            if key != "manifest_semantic_id"
        }
    return _digest(b"RDX-MANIFEST-SEM-1", _m8g_fv3(dict(manifest)))


def validate_manifest(manifest: Mapping[str, Any], body: CompactBody) -> None:
    required = _MANIFEST_FIELDS | {"manifest_semantic_id"}
    if set(manifest) != required:
        raise M8GError("manifest_fields_invalid")
    if (
        manifest["schema_version"] != MANIFEST_SCHEMA
        or manifest["profile"] != body.profile
    ):
        raise M8GError("manifest_profile_invalid")
    if manifest["body_semantic_id"] != body.semantic_id:
        raise M8GError("manifest_body_semantic_mismatch")
    if (
        not isinstance(manifest["selected_example_id"], str)
        or not manifest["selected_example_id"]
        or type(manifest["selected_position"]) is not int
        or manifest["selected_position"] < 0
        or not isinstance(manifest["source_passport_id"], str)
        or not manifest["source_passport_id"]
        or any(
            value is not None and (not isinstance(value, str) or not value)
            for value in (
                manifest["corridor_mode_id"],
                manifest["corridor_fingerprint_id"],
            )
        )
        or not isinstance(manifest["package_role"], str)
        or manifest["package_role"] != manifest["profile"]
    ):
        raise M8GError("manifest_field_type_invalid")
    if (
        not isinstance(manifest["body_raw_digest"], bytes)
        or len(manifest["body_raw_digest"]) != 32
        or not isinstance(manifest["authority_id"], bytes)
        or len(manifest["authority_id"]) != 32
        or not isinstance(manifest["selection_authority_id"], bytes)
        or len(manifest["selection_authority_id"]) != 32
        or not isinstance(manifest["selection_obligations"], list)
        or type(manifest["selection_obligation_count"]) is not int
        or manifest["selection_obligation_count"] < 0
        or manifest["selection_obligation_count"]
        != len(manifest["selection_obligations"])
    ):
        raise M8GError("manifest_binding_fields_invalid")
    if manifest["body_raw_digest"] != body_raw_digest(encode_compact_body(body)):
        raise M8GError("manifest_body_raw_mismatch")
    if any(
        not isinstance(item, Mapping)
        or set(item) != {"role", "source_id", "rank", "score", "collision_kind"}
        or item["role"] not in {1, 2}
        or not isinstance(item["source_id"], str)
        or not isinstance(item["rank"], int)
        or isinstance(item["rank"], bool)
        or item["rank"] < 1
        or item["score"] is not None
        and (type(item["score"]) is not float or not math.isfinite(item["score"]))
        or item["collision_kind"] not in {0, 1, 2}
        for item in manifest["selection_obligations"]
    ):
        raise M8GError("manifest_obligations_invalid")
    if manifest["manifest_semantic_id"] != manifest_semantic_id(manifest):
        raise M8GError("manifest_digest_invalid")


def validate_transition(current: JournalState, proposed: JournalState) -> None:
    if proposed != current and _NEXT.get(current) != proposed:
        raise M8GError("journal_transition_invalid")
