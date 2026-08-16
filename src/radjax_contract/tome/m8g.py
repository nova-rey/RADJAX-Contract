"""Opt-in M8G compact-body and immutable-body Contract primitives.

This module is deliberately additive: legacy v1-v3 padded records remain
validated by their existing modules.  M8G resources are closed, explicit
flavors and never inferred from a producer command or pathname.
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from radjax_contract.tome.v3.codec import fv3

COMPACT_SCHEMA = "selected_exemplar_payload_compact_v1"
BODY_SCHEMA = "selected_exemplar_body_v1"
MANIFEST_SCHEMA = "selected_exemplar_manifest_v1"
M8G_VERSION = "radjax_contract_m8g_v1"
PROFILE_CODES = {1: "student", 2: "full_debug", 3: "producer_evidence"}
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


def _digest(label: bytes, payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(label + payload).hexdigest()


def _raw_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _finite(values: Sequence[float], field: str) -> None:
    if any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        for value in values
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
            if not math.isclose(
                sum(probs) + self.tail_mass[index], 1.0, rel_tol=2e-5, abs_tol=2e-5
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
    def semantic_id(self) -> str:
        return _digest(b"RDX-BODY-SEM-1", fv3(self.projection()))


def compact_from_padded(padded: Mapping[str, Any], *, profile: str) -> CompactBody:
    """Project one padded record without changing active ordering or values."""

    mask = padded.get("top_selection_mask")
    ids = padded.get("top_token_ids")
    probs = padded.get("top_probs")
    logs = padded.get("top_log_probs")
    if not all(isinstance(value, Sequence) for value in (mask, ids, probs, logs)):
        raise M8GError("padded_fields_missing")
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

    payload = fv3(body.projection())
    header = struct.pack(
        ">4sHHIIIIQQ",
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
    return header + payload


def body_raw_digest(body_bytes: bytes) -> str:
    if not body_bytes.startswith(MAGIC):
        raise M8GError("body_magic_invalid")
    return _raw_digest(body_bytes)


def validate_body_bytes(body_bytes: bytes, *, profile: str) -> CompactBody:
    if len(body_bytes) < 40 or not body_bytes.startswith(MAGIC):
        raise M8GError("body_truncated_or_magic_invalid")
    _, version, profile_code, _, _, _, _, payload_size, _ = struct.unpack(
        ">4sHHIIIIQQ", body_bytes[:40]
    )
    if version != 1 or PROFILE_CODES.get(profile_code) != profile:
        raise M8GError("body_profile_invalid")
    payload = body_bytes[40:]
    if len(payload) != payload_size:
        raise M8GError("body_payload_size_mismatch")
    value, offset = _decode_fv3(payload, 0)
    if offset != len(payload) or not isinstance(value, Mapping):
        raise M8GError("body_projection_invalid")
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
    if tag == 0x20:
        if offset + 8 > len(value):
            raise M8GError("fv3_truncated")
        size = int.from_bytes(value[offset : offset + 8], "big")
        offset += 8
        if offset + size > len(value):
            raise M8GError("fv3_truncated")
        return value[offset : offset + size].decode("utf-8"), offset + size
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


def manifest_semantic_id(manifest: Mapping[str, Any]) -> str:
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise M8GError("manifest_schema_invalid")
    if "manifest_semantic_id" in manifest:
        manifest = {
            key: value
            for key, value in manifest.items()
            if key != "manifest_semantic_id"
        }
    return _digest(b"RDX-MANIFEST-SEM-1", fv3(dict(manifest)))


def validate_manifest(manifest: Mapping[str, Any], body: CompactBody) -> None:
    required = {
        "schema_version",
        "profile",
        "selected_example_id",
        "selected_position",
        "body_semantic_id",
        "body_raw_digest",
        "selection_authority_id",
        "manifest_semantic_id",
    }
    if set(manifest) != required:
        raise M8GError("manifest_fields_invalid")
    if (
        manifest["schema_version"] != MANIFEST_SCHEMA
        or manifest["profile"] != body.profile
    ):
        raise M8GError("manifest_profile_invalid")
    if manifest["body_semantic_id"] != body.semantic_id:
        raise M8GError("manifest_body_semantic_mismatch")
    if manifest["manifest_semantic_id"] != manifest_semantic_id(manifest):
        raise M8GError("manifest_digest_invalid")


def validate_transition(current: JournalState, proposed: JournalState) -> None:
    if proposed != current and _NEXT.get(current) != proposed:
        raise M8GError("journal_transition_invalid")
