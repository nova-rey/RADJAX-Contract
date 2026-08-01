#!/usr/bin/env python3
# ruff: noqa: E501
"""Stdlib-only portable validator for the published M7 streaming contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
import tarfile
import tempfile
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

PREFIX = "sha256:"
PROFILES = {"unpacked", "student", "full_debug_provenance"}
TRANSPORTS = {"directory", "rtome", "tgz"}
CLASSIFICATIONS = {
    "training_critical",
    "integrity_or_provenance",
    "diagnostic",
    "human_readable",
    "operational",
}
CHUNK = 1 << 16
SEMANTIC_FIELDS = {
    "selected_example_id",
    "selected_position",
    "selected_score",
    "score_selected_position_entropy",
    "score_top_token_id",
    "source_shard_id",
    "source_row",
    "source_position",
    "source_score",
    "source_top_token_id",
    "source_score_policy",
    "payload_ref",
    "selected_policy",
    "source_delivery_path",
    "top_token_ids",
    "top_log_probs",
    "top_probs",
    "top_selection_mask",
    "effective_top_k",
    "top_mass",
    "tail_mass",
    "bucket_masses",
    "teacher_entropy",
    "sequence_length",
    "vocab_size",
    "num_buckets",
    "dynamic_top_k",
    "dynamic_mass_threshold",
    "dynamic_top_k_max",
    "top_k_saturated",
    "long_tail_class",
    "long_tail_warnings",
    "effective_top_k_fraction_of_vocab",
    "semantic_tail_tag",
    "selected_board",
    "corridor_mode_id",
    "corridor_fingerprint_id",
    "corridor_assignment_status",
}
INTEGER_FIELDS = {
    "selected_position",
    "score_top_token_id",
    "source_shard_id",
    "source_row",
    "source_position",
    "source_top_token_id",
    "effective_top_k",
    "sequence_length",
    "vocab_size",
    "num_buckets",
    "dynamic_top_k_max",
}
NUMBER_FIELDS = {
    "selected_score",
    "score_selected_position_entropy",
    "source_score",
    "top_mass",
    "tail_mass",
    "teacher_entropy",
    "dynamic_mass_threshold",
    "effective_top_k_fraction_of_vocab",
}
STRING_FIELDS = {
    "selected_example_id",
    "source_score_policy",
    "selected_policy",
    "source_delivery_path",
    "long_tail_class",
    "semantic_tail_tag",
    "selected_board",
    "corridor_assignment_status",
}
EXTENSION_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Result:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class StreamingTomeDescriptor:
    """Validated-at-open metadata available to a sequential consumer.

    The payload itself is deliberately not part of this descriptor: callers
    consume it through :class:`StreamingTomeReader` one JSONL record at a
    time.  ``semantic_identity`` is the compact v4 identity object from the
    cover, retained verbatim after its digest has been checked.
    """

    profile: str
    transport: str
    semantic_identity: dict[str, Any]
    selected_count: int


class StreamingTomeReader:
    """Context-managed direct sequential reader for a canonical v4 archive.

    Construction consumes only the cover/header/inventory prelude.  Payload
    records are yielded while their shard, index, identity, and manifest
    obligations are checked.  Closing before exhaustion is intentionally an
    incomplete verification, never a successful whole-package result.
    """

    def __init__(self, path: Path, *, strict: bool = False) -> None:
        if path.is_dir():
            raise ContractError("streaming_directory_requires_extracted_reader")
        self._archive_reader = _ArchiveStreamingReader(path, strict=strict)
        self.descriptor = self._archive_reader.descriptor

    @property
    def verification_state(self) -> str:
        return self._archive_reader.verification_state

    @property
    def warnings(self) -> tuple[str, ...]:
        return self._archive_reader.warnings

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._archive_reader)

    def close(self) -> None:
        self._archive_reader.close()

    def __enter__(self) -> StreamingTomeReader:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("shape_invalid") from exc
    if not isinstance(value, dict):
        raise ContractError("shape_invalid")
    return value


def _digest_path(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            while block := handle.read(CHUNK):
                digest.update(block)
                size += len(block)
    except OSError as exc:
        raise ContractError("transport_corrupt") from exc
    return PREFIX + digest.hexdigest(), size


def _sha(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith(PREFIX):
        raise ContractError("digest_syntax_invalid")
    if any(char not in "0123456789abcdef" for char in value[len(PREFIX) :]):
        raise ContractError("digest_syntax_invalid")
    return value


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ContractError("path_unsafe")
    parsed = PurePosixPath(value)
    if (
        parsed.is_absolute()
        or value != parsed.as_posix()
        or any(part in {".", ".."} for part in parsed.parts)
    ):
        raise ContractError("path_unsafe")
    return value


def _canonical(value: Any) -> str:
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ContractError("shape_invalid") from exc
    return PREFIX + hashlib.sha256(encoded).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ContractError("shape_invalid") from exc


def _nonnegative_int(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractError("shape_invalid")
    return value


def _finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError("payload_nonfinite_number")
    if isinstance(value, dict):
        for child in value.values():
            _finite(child)
    elif isinstance(value, list):
        for child in value:
            _finite(child)


class _SequenceDigest:
    """Constant-space hasher for the canonical sequence-digest JSON value."""

    def __init__(self) -> None:
        self._digest = hashlib.sha256()
        self._digest.update(b'{"records":[')
        self._first = True

    def add(self, record: dict[str, str]) -> None:
        if not self._first:
            self._digest.update(b",")
        self._digest.update(_canonical_bytes(record))
        self._first = False

    def finish(self) -> str:
        self._digest.update(
            b'],"schema_version":"selected_exemplar_payload_sequence_v1"}'
        )
        return PREFIX + self._digest.hexdigest()


def _semantic_record(record: Any) -> tuple[str, str]:
    if not isinstance(record, dict) or not SEMANTIC_FIELDS <= set(record):
        raise ContractError("payload_semantic_projection_invalid")
    allowed = SEMANTIC_FIELDS | {"opaque_extensions"}
    if set(record) - allowed:
        raise ContractError("payload_semantic_projection_invalid")
    _finite(record)
    for field in INTEGER_FIELDS:
        if not isinstance(record[field], int) or isinstance(record[field], bool):
            raise ContractError("payload_semantic_projection_invalid")
    for field in NUMBER_FIELDS:
        if not isinstance(record[field], (int, float)) or isinstance(
            record[field], bool
        ):
            raise ContractError("payload_semantic_projection_invalid")
    for field in STRING_FIELDS:
        if not isinstance(record[field], str) or not record[field]:
            raise ContractError("payload_semantic_projection_invalid")
    if record["sequence_length"] < 1 or record["vocab_size"] < 1:
        raise ContractError("payload_semantic_projection_invalid")
    if record["num_buckets"] < 0 or record["dynamic_top_k_max"] < 1:
        raise ContractError("payload_semantic_projection_invalid")
    if not isinstance(record["payload_ref"], dict):
        raise ContractError("payload_semantic_projection_invalid")
    for name in ("top_token_ids",):
        if not isinstance(record[name], list) or any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in record[name]
        ):
            raise ContractError("payload_semantic_projection_invalid")
    for name in ("top_log_probs", "top_probs", "bucket_masses"):
        if not isinstance(record[name], list) or any(
            not isinstance(value, (int, float)) or isinstance(value, bool)
            for value in record[name]
        ):
            raise ContractError("payload_semantic_projection_invalid")
    if not isinstance(record["top_selection_mask"], list) or any(
        not isinstance(value, bool) for value in record["top_selection_mask"]
    ):
        raise ContractError("payload_semantic_projection_invalid")
    if not isinstance(record["dynamic_top_k"], (bool, dict)):
        raise ContractError("payload_semantic_projection_invalid")
    if not isinstance(record["top_k_saturated"], bool):
        raise ContractError("payload_semantic_projection_invalid")
    if not isinstance(record["long_tail_warnings"], list) or any(
        not isinstance(value, str) for value in record["long_tail_warnings"]
    ):
        raise ContractError("payload_semantic_projection_invalid")
    for name in ("corridor_mode_id", "corridor_fingerprint_id"):
        if not isinstance(record[name], (str, int)) or isinstance(record[name], bool):
            raise ContractError("payload_semantic_projection_invalid")
    extensions = record.get("opaque_extensions", {})
    if not isinstance(extensions, dict):
        raise ContractError("opaque_extension_undocumented")
    for name, extension in extensions.items():
        if not EXTENSION_NAME.fullmatch(name) or not isinstance(extension, dict):
            raise ContractError("opaque_extension_undocumented")
        _require(extension, {"schema_id", "value", "semantic_digest"})
        if not isinstance(extension["schema_id"], str) or not extension["schema_id"]:
            raise ContractError("opaque_extension_undocumented")
        _finite(extension["value"])
        if _canonical(extension["value"]) != _sha(extension["semantic_digest"]):
            raise ContractError("opaque_extension_undocumented")
    logical_id = _canonical(
        {
            "selected_example_id": record["selected_example_id"],
            "selected_position": record["selected_position"],
        }
    )
    return logical_id, _canonical(record)


def _inside(root: Path, relative: str) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        raise ContractError("path_unsafe")
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ContractError("path_unsafe") from exc
    return candidate


def _lines(path: Path) -> Iterator[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    raise ContractError("shape_invalid")
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ContractError("shape_invalid")
                yield value
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("shape_invalid") from exc


def _require(value: dict[str, Any], keys: set[str]) -> None:
    if set(value) != keys:
        raise ContractError("shape_invalid")


def _validate_identity(identity: Any) -> dict[str, Any]:
    if not isinstance(identity, dict):
        raise ContractError("payload_semantic_projection_invalid")
    _require(
        identity,
        {
            "schema_version",
            "payload_sequence_digest",
            "selected_count",
            "nonselected_training_payload",
            "training_contract",
            "authority",
            "semantic_digest",
        },
    )
    if identity["schema_version"] != "radjax_tome_semantic_identity_v2":
        raise ContractError("schema_version_unsupported")
    _sha(identity["payload_sequence_digest"])
    _nonnegative_int(identity["selected_count"])
    payload = identity["nonselected_training_payload"]
    if not isinstance(payload, list):
        raise ContractError("payload_semantic_projection_invalid")
    previous = ""
    for entry in payload:
        if not isinstance(entry, dict):
            raise ContractError("payload_semantic_projection_invalid")
        _require(entry, {"logical_id", "semantic_digest"})
        logical_id = entry["logical_id"]
        if not isinstance(logical_id, str) or not logical_id or logical_id <= previous:
            raise ContractError("payload_semantic_projection_invalid")
        previous = logical_id
        _sha(entry["semantic_digest"])
    if not isinstance(identity["training_contract"], dict) or not isinstance(
        identity["authority"], dict
    ):
        raise ContractError("payload_semantic_projection_invalid")
    _finite(identity["training_contract"])
    _finite(identity["authority"])
    expected = _canonical(
        {key: value for key, value in identity.items() if key != "semantic_digest"}
    )
    if expected != _sha(identity["semantic_digest"]):
        raise ContractError("payload_semantic_projection_invalid")
    return identity


def _validate_selected_payloads(
    root: Path, listed: set[str], identity: dict[str, Any]
) -> None:
    layout_path = "selected_exemplars/payload-layout.json"
    if layout_path not in listed:
        raise ContractError("profile_inventory_mismatch")
    layout = _json(_inside(root, layout_path))
    _require(
        layout,
        {
            "schema_version",
            "layout_version",
            "payload_index",
            "shard_index",
            "sequence_digest",
            "selected_count",
            "payload_records_per_shard",
        },
    )
    if (
        layout["schema_version"] != "radjax_tome_payload_layout_v1"
        or layout["layout_version"] != "selected_payload_shards_v1"
    ):
        raise ContractError("schema_version_unsupported")
    selected_count = _nonnegative_int(layout["selected_count"])
    capacity = _nonnegative_int(layout["payload_records_per_shard"])
    if capacity < 1:
        raise ContractError("shape_invalid")
    _sha(layout["sequence_digest"])
    index_ref = layout["payload_index"]
    if not isinstance(index_ref, dict):
        raise ContractError("shape_invalid")
    _require(
        index_ref, {"path", "sha256", "size_bytes", "record_count", "schema_version"}
    )
    if index_ref["schema_version"] != "radjax_tome_payload_index_v2":
        raise ContractError("schema_version_unsupported")
    index_path = _path(index_ref["path"])
    if (
        index_path != "selected_exemplars/payload-index.jsonl"
        or index_path not in listed
    ):
        raise ContractError("payload_index_address_invalid")
    if _digest_path(_inside(root, index_path)) != (
        _sha(index_ref["sha256"]),
        _nonnegative_int(index_ref["size_bytes"]),
    ):
        raise ContractError("digest_mismatch")
    index_count = _nonnegative_int(index_ref["record_count"])
    shard_ref = layout["shard_index"]
    if not isinstance(shard_ref, dict):
        raise ContractError("shape_invalid")
    _require(
        shard_ref, {"path", "sha256", "size_bytes", "record_count", "schema_version"}
    )
    if shard_ref["schema_version"] != "radjax_tome_payload_shard_index_v1":
        raise ContractError("schema_version_unsupported")
    shard_index_path = _path(shard_ref["path"])
    if (
        shard_index_path != "selected_exemplars/payload-shards.jsonl"
        or shard_index_path not in listed
    ):
        raise ContractError("payload_index_address_invalid")
    if _digest_path(_inside(root, shard_index_path)) != (
        _sha(shard_ref["sha256"]),
        _nonnegative_int(shard_ref["size_bytes"]),
    ):
        raise ContractError("digest_mismatch")
    shard_count = _nonnegative_int(shard_ref["record_count"])
    index_iter = iter(_lines(_inside(root, index_path)))
    overall_digest = _SequenceDigest()
    expected_selection = 0
    index_seen = 0
    seen_tmp = tempfile.TemporaryDirectory(prefix="radjax-tome-v2-ids-")
    seen = sqlite3.connect(Path(seen_tmp.name) / "logical-ids.sqlite3")
    seen.execute("CREATE TABLE ids (logical_id TEXT PRIMARY KEY)")
    shard_seen_count = 0
    for shard_position, shard in enumerate(_lines(_inside(root, shard_index_path))):
        shard_seen_count += 1
        _require(
            shard,
            {
                "shard_id",
                "path",
                "sha256",
                "size_bytes",
                "first_selection_index",
                "last_selection_index",
                "record_count",
                "semantic_digest",
            },
        )
        shard_id = _nonnegative_int(shard["shard_id"])
        record_count = _nonnegative_int(shard["record_count"])
        first = _nonnegative_int(shard["first_selection_index"])
        last = _nonnegative_int(shard["last_selection_index"])
        if shard_id != shard_position or record_count < 1 or record_count > capacity:
            raise ContractError("payload_index_address_invalid")
        if first != expected_selection or last != first + record_count - 1:
            raise ContractError("payload_index_address_invalid")
        shard_path = _path(shard["path"])
        if shard_path not in listed:
            raise ContractError("profile_inventory_mismatch")
        if _digest_path(_inside(root, shard_path)) != (
            _sha(shard["sha256"]),
            _nonnegative_int(shard["size_bytes"]),
        ):
            raise ContractError("digest_mismatch")
        shard_digest = _SequenceDigest()
        shard_seen = 0
        for row, payload in enumerate(_lines(_inside(root, shard_path))):
            if row >= record_count:
                raise ContractError("manifest_record_count_mismatch")
            try:
                index = next(index_iter)
            except StopIteration as exc:
                raise ContractError("manifest_record_count_mismatch") from exc
            index_seen += 1
            _require(
                index,
                {
                    "logical_id",
                    "selected_example_id",
                    "selected_position",
                    "selection_index",
                    "shard_id",
                    "row",
                    "payload_sha256",
                    "payload_semantic_digest",
                    "shard_sha256",
                },
            )
            logical_id, semantic_digest = _semantic_record(payload)
            if (
                index.get("logical_id") != logical_id
                or index.get("selected_example_id") != payload["selected_example_id"]
                or index.get("selected_position") != payload["selected_position"]
                or _nonnegative_int(index.get("selection_index")) != expected_selection
                or _nonnegative_int(index.get("shard_id")) != shard_id
                or _nonnegative_int(index.get("row")) != row
                or _sha(index.get("payload_sha256")) != _canonical(payload)
                or _sha(index.get("shard_sha256")) != shard["sha256"]
            ):
                raise ContractError("payload_index_address_invalid")
            if _sha(index.get("payload_semantic_digest")) != semantic_digest:
                raise ContractError("payload_semantic_projection_invalid")
            try:
                seen.execute("INSERT INTO ids VALUES (?)", (logical_id,))
            except sqlite3.IntegrityError as exc:
                raise ContractError("payload_index_address_invalid") from exc
            record = {
                "logical_id": logical_id,
                "payload_semantic_digest": semantic_digest,
            }
            shard_digest.add(record)
            overall_digest.add(record)
            shard_seen += 1
            expected_selection += 1
        if shard_seen != record_count:
            raise ContractError("manifest_record_count_mismatch")
        if shard_digest.finish() != _sha(shard["semantic_digest"]):
            raise ContractError("payload_sequence_digest_mismatch")
    try:
        next(index_iter)
    except StopIteration:
        pass
    else:
        raise ContractError("manifest_record_count_mismatch")
    if (
        index_seen != index_count
        or expected_selection != selected_count
        or shard_seen_count != shard_count
    ):
        raise ContractError("manifest_record_count_mismatch")
    sequence_digest = overall_digest.finish()
    if sequence_digest != _sha(layout["sequence_digest"]):
        raise ContractError("payload_sequence_digest_mismatch")
    if (
        selected_count != identity["selected_count"]
        or sequence_digest != identity["payload_sequence_digest"]
    ):
        raise ContractError("payload_semantic_projection_invalid")
    seen.close()
    seen_tmp.cleanup()


def validate_directory(root: Path) -> Result:
    try:
        cover = _json(root / "cover_page.json")
        _require(
            cover,
            {
                "schema_version",
                "identity",
                "training",
                "package",
                "manifests",
                "authority",
                "provenance",
                "validation",
            },
        )
        if cover["schema_version"] != "radjax_tome_cover_v4":
            raise ContractError("schema_version_unsupported")
        package = cover["package"]
        manifests = cover["manifests"]
        if (
            not isinstance(package, dict)
            or set(package) != {"profile", "transport"}
            or package.get("profile") not in PROFILES
            or package.get("transport") not in TRANSPORTS
        ):
            raise ContractError("profile_inventory_mismatch")
        if not isinstance(manifests, dict) or set(manifests) != {"header"}:
            raise ContractError("shape_invalid")
        ref = manifests["header"]
        if not isinstance(ref, dict):
            raise ContractError("shape_invalid")
        if (
            set(ref) != {"path", "sha256", "size_bytes", "schema_version"}
            or ref.get("schema_version") != "tome_content_manifest_header_v3"
        ):
            raise ContractError("shape_invalid")
        header_path = _path(ref.get("path"))
        if header_path != "manifests/content-manifest-header.json":
            raise ContractError("shape_invalid")
        if _digest_path(_inside(root, header_path)) != (
            _sha(ref.get("sha256")),
            ref.get("size_bytes"),
        ):
            raise ContractError("digest_mismatch")
        header = _json(_inside(root, header_path))
        _require(
            header,
            {
                "schema_version",
                "profile",
                "semantic_identity_digest",
                "inventory_path",
                "inventory_sha256",
                "inventory_size_bytes",
                "entry_count",
            },
        )
        if (
            header["schema_version"] != "tome_content_manifest_header_v3"
            or header["profile"] != package["profile"]
        ):
            raise ContractError("profile_inventory_mismatch")
        inventory_path = _path(header["inventory_path"])
        if inventory_path != "manifests/content-manifest-inventory.jsonl":
            raise ContractError("shape_invalid")
        _sha(header["semantic_identity_digest"])
        if _digest_path(_inside(root, inventory_path)) != (
            _sha(header["inventory_sha256"]),
            header["inventory_size_bytes"],
        ):
            raise ContractError("digest_mismatch")
        previous = ""
        count = 0
        listed: set[str] = set()
        for entry in _lines(_inside(root, inventory_path)):
            _require(
                entry,
                {
                    "path",
                    "sha256",
                    "size_bytes",
                    "classification",
                    "training_authoritative",
                },
            )
            path = _path(entry["path"])
            if path <= previous or path in {
                "cover_page.json",
                header_path,
                inventory_path,
            }:
                raise ContractError("ordering_invalid")
            previous, count = path, count + 1
            listed.add(path)
            if not isinstance(entry["size_bytes"], int) or isinstance(
                entry["size_bytes"], bool
            ):
                raise ContractError("shape_invalid")
            if entry["classification"] not in CLASSIFICATIONS or not isinstance(
                entry["training_authoritative"], bool
            ):
                raise ContractError("shape_invalid")
            if _digest_path(_inside(root, path)) != (
                _sha(entry["sha256"]),
                entry["size_bytes"],
            ):
                raise ContractError("digest_mismatch")
        if count != header["entry_count"]:
            raise ContractError("profile_inventory_mismatch")
        observed = {
            p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
        }
        if observed != listed | {"cover_page.json", header_path, inventory_path}:
            raise ContractError("profile_inventory_mismatch")
        identity = _validate_identity(cover["identity"])
        if (
            header["semantic_identity_digest"] != identity["semantic_digest"]
            or cover["training"] != identity["training_contract"]
            or cover["authority"] != identity["authority"]
        ):
            raise ContractError("payload_semantic_projection_invalid")
        _validate_selected_payloads(root, listed, identity)
        return Result(True)
    except ContractError as exc:
        return Result(False, (exc.code,))


def _digest_stream(source: BinaryIO) -> tuple[str, int]:
    """Digest a member without an unbounded read or an in-memory copy."""

    digest = hashlib.sha256()
    size = 0
    while block := source.read(CHUNK):
        digest.update(block)
        size += len(block)
    return PREFIX + digest.hexdigest(), size


def read_extracted_payload_record(
    root: Path, *, shard_id: int, row: int
) -> dict[str, Any]:
    """Read one v4 payload record from a validated extracted directory.

    This is deliberately unavailable for an archive wrapper: the Contract only
    promises direct sequential archive consumption.  It validates the cover,
    manifest control plane, payload layout/index, and the requested shard; it
    never opens preceding or following payload shards.
    """

    if not root.is_dir():
        raise ContractError("random_access_transport_unsupported")
    if not isinstance(shard_id, int) or isinstance(shard_id, bool) or shard_id < 0:
        raise ContractError("payload_index_address_invalid")
    if not isinstance(row, int) or isinstance(row, bool) or row < 0:
        raise ContractError("payload_index_address_invalid")
    cover = _json(root / "cover_page.json")
    _require(
        cover,
        {
            "schema_version",
            "identity",
            "training",
            "package",
            "manifests",
            "authority",
            "provenance",
            "validation",
        },
    )
    if cover["schema_version"] != "radjax_tome_cover_v4":
        raise ContractError("schema_version_unsupported")
    package = cover["package"]
    if (
        not isinstance(package, dict)
        or set(package) != {"profile", "transport"}
        or package.get("profile") not in PROFILES
        or package.get("transport") != "directory"
    ):
        raise ContractError("transport_mismatch")
    identity = _validate_identity(cover["identity"])
    if (
        cover["training"] != identity["training_contract"]
        or cover["authority"] != identity["authority"]
    ):
        raise ContractError("payload_semantic_projection_invalid")
    manifests = cover["manifests"]
    if not isinstance(manifests, dict) or set(manifests) != {"header"}:
        raise ContractError("shape_invalid")
    header_ref = manifests["header"]
    if not isinstance(header_ref, dict):
        raise ContractError("shape_invalid")
    _require(header_ref, {"path", "sha256", "size_bytes", "schema_version"})
    header_path = _path(header_ref["path"])
    if (
        header_path != "manifests/content-manifest-header.json"
        or header_ref["schema_version"] != "tome_content_manifest_header_v3"
    ):
        raise ContractError("shape_invalid")
    if _digest_path(_inside(root, header_path)) != (
        _sha(header_ref["sha256"]),
        _nonnegative_int(header_ref["size_bytes"]),
    ):
        raise ContractError("digest_mismatch")
    header = _json(_inside(root, header_path))
    _require(
        header,
        {
            "schema_version",
            "profile",
            "semantic_identity_digest",
            "inventory_path",
            "inventory_sha256",
            "inventory_size_bytes",
            "entry_count",
        },
    )
    inventory_path = _path(header["inventory_path"])
    if (
        header["schema_version"] != "tome_content_manifest_header_v3"
        or header["profile"] != package["profile"]
        or inventory_path != "manifests/content-manifest-inventory.jsonl"
        or header["semantic_identity_digest"] != identity["semantic_digest"]
    ):
        raise ContractError("profile_inventory_mismatch")
    if _digest_path(_inside(root, inventory_path)) != (
        _sha(header["inventory_sha256"]),
        _nonnegative_int(header["inventory_size_bytes"]),
    ):
        raise ContractError("digest_mismatch")
    inventory: dict[str, dict[str, Any]] = {}
    previous = ""
    for entry in _lines(_inside(root, inventory_path)):
        _require(
            entry,
            {
                "path",
                "sha256",
                "size_bytes",
                "classification",
                "training_authoritative",
            },
        )
        path = _path(entry["path"])
        if path <= previous:
            raise ContractError("ordering_invalid")
        previous = path
        inventory[path] = entry
    layout_path = "selected_exemplars/payload-layout.json"
    index_path = "selected_exemplars/payload-index.jsonl"
    shard_index_path = "selected_exemplars/payload-shards.jsonl"
    if not {layout_path, index_path, shard_index_path} <= set(inventory):
        raise ContractError("profile_inventory_mismatch")
    for path in (layout_path, index_path, shard_index_path):
        entry = inventory[path]
        if _digest_path(_inside(root, path)) != (
            _sha(entry["sha256"]),
            _nonnegative_int(entry["size_bytes"]),
        ):
            raise ContractError("digest_mismatch")
    layout = _json(_inside(root, layout_path))
    _require(
        layout,
        {
            "schema_version",
            "layout_version",
            "payload_index",
            "shard_index",
            "sequence_digest",
            "selected_count",
            "payload_records_per_shard",
        },
    )
    if (
        layout["schema_version"] != "radjax_tome_payload_layout_v1"
        or layout["layout_version"] != "selected_payload_shards_v1"
    ):
        raise ContractError("schema_version_unsupported")
    target_shard: dict[str, Any] | None = None
    for position, entry in enumerate(_lines(_inside(root, shard_index_path))):
        _require(
            entry,
            {
                "shard_id",
                "path",
                "sha256",
                "size_bytes",
                "first_selection_index",
                "last_selection_index",
                "record_count",
                "semantic_digest",
            },
        )
        if _nonnegative_int(entry["shard_id"]) != position:
            raise ContractError("payload_index_address_invalid")
        if position == shard_id:
            target_shard = entry
            break
    if target_shard is None or row >= _nonnegative_int(target_shard["record_count"]):
        raise ContractError("payload_index_address_invalid")
    target_path = _path(target_shard["path"])
    if target_path not in inventory:
        raise ContractError("profile_inventory_mismatch")
    target_inventory = inventory[target_path]
    expected_digest = _sha(target_shard["sha256"])
    if expected_digest != _sha(target_inventory["sha256"]) or _digest_path(
        _inside(root, target_path)
    ) != (
        expected_digest,
        _nonnegative_int(target_shard["size_bytes"]),
    ):
        raise ContractError("digest_mismatch")
    expected_index: dict[str, Any] | None = None
    for entry in _lines(_inside(root, index_path)):
        if entry.get("shard_id") == shard_id and entry.get("row") == row:
            expected_index = entry
            break
    if expected_index is None:
        raise ContractError("payload_index_address_invalid")
    for actual_row, payload in enumerate(_lines(_inside(root, target_path))):
        if actual_row != row:
            continue
        logical_id, semantic_digest = _semantic_record(payload)
        if (
            expected_index.get("logical_id") != logical_id
            or expected_index.get("selected_example_id")
            != payload["selected_example_id"]
            or expected_index.get("selected_position") != payload["selected_position"]
            or _sha(expected_index.get("payload_sha256")) != _canonical(payload)
            or _sha(expected_index.get("payload_semantic_digest")) != semantic_digest
            or _sha(expected_index.get("shard_sha256")) != expected_digest
        ):
            raise ContractError("payload_index_address_invalid")
        return payload
    raise ContractError("manifest_record_count_mismatch")


def _read_small_member(source: BinaryIO, *, limit: int = 8 << 20) -> bytes:
    """Read bounded control-plane JSON; payload JSONL never uses this path."""

    blocks: list[bytes] = []
    size = 0
    while block := source.read(CHUNK):
        size += len(block)
        if size > limit:
            raise ContractError("shape_invalid")
        blocks.append(block)
    return b"".join(blocks)


def _json_bytes(value: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("shape_invalid") from exc
    if not isinstance(parsed, dict):
        raise ContractError("shape_invalid")
    return parsed


def _copy_member_to_temp(source: BinaryIO, destination: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with destination.open("wb") as handle:
        while block := source.read(CHUNK):
            handle.write(block)
            digest.update(block)
            size += len(block)
    return PREFIX + digest.hexdigest(), size


def _check_member_metadata(member: tarfile.TarInfo) -> bool:
    """Return whether a safe member has producer-canonical tar metadata."""

    if not member.isfile() or member.issym() or member.islnk():
        raise ContractError("transport_unsafe")
    return (
        member.mtime == 0
        and member.uid == 0
        and member.gid == 0
        and member.uname == ""
        and member.gname == ""
        and member.mode == 0o644
    )


def _archive_transport(path: Path) -> tuple[str, bool]:
    """Identify the physical wrapper and its gzip canonicality cheaply."""

    try:
        with path.open("rb") as handle:
            header = handle.read(10)
    except OSError as exc:
        raise ContractError("transport_corrupt") from exc
    if len(header) < 2:
        raise ContractError("transport_corrupt")
    if header[:2] != b"\x1f\x8b":
        return "rtome", True
    if len(header) < 10:
        raise ContractError("transport_corrupt")
    flags = header[3]
    # FEXTRA/FNAME/FCOMMENT change producer bytes but remain safe to consume.
    canonical = header[4:8] == b"\0\0\0\0" and not flags & 0x1C
    return "tgz", canonical


class _InventoryCursor:
    """Disk-backed, one-entry-at-a-time inventory cursor for archive order."""

    def __init__(self, path: Path, *, header_path: str, inventory_path: str) -> None:
        self._iterator = _lines(path)
        self._previous = ""
        self._count = 0
        self._header_path = header_path
        self._inventory_path = inventory_path

    def next(self) -> dict[str, Any]:
        try:
            entry = next(self._iterator)
        except StopIteration as exc:
            raise ContractError("profile_inventory_mismatch") from exc
        _require(
            entry,
            {
                "path",
                "sha256",
                "size_bytes",
                "classification",
                "training_authoritative",
            },
        )
        path = _path(entry["path"])
        if path <= self._previous or path in {
            "cover_page.json",
            self._header_path,
            self._inventory_path,
        }:
            raise ContractError("ordering_invalid")
        self._previous = path
        self._count += 1
        if (
            not isinstance(entry["size_bytes"], int)
            or isinstance(entry["size_bytes"], bool)
            or entry["classification"] not in CLASSIFICATIONS
            or not isinstance(entry["training_authoritative"], bool)
        ):
            raise ContractError("shape_invalid")
        entry["path"] = path
        entry["sha256"] = _sha(entry["sha256"])
        return entry

    def finish(self, expected_count: int) -> None:
        try:
            next(self._iterator)
        except StopIteration:
            pass
        else:
            raise ContractError("profile_inventory_mismatch")
        if self._count != expected_count:
            raise ContractError("profile_inventory_mismatch")


class _ArchivePayloadValidator:
    """Streaming payload/index checker; indexes live on temporary disk only."""

    def __init__(
        self, root: Path, layout: dict[str, Any], identity: dict[str, Any]
    ) -> None:
        _require(
            layout,
            {
                "schema_version",
                "layout_version",
                "payload_index",
                "shard_index",
                "sequence_digest",
                "selected_count",
                "payload_records_per_shard",
            },
        )
        if (
            layout["schema_version"] != "radjax_tome_payload_layout_v1"
            or layout["layout_version"] != "selected_payload_shards_v1"
        ):
            raise ContractError("schema_version_unsupported")
        self.layout = layout
        self.identity = identity
        self.capacity = _nonnegative_int(layout["payload_records_per_shard"])
        if self.capacity < 1:
            raise ContractError("shape_invalid")
        self.selected_count = _nonnegative_int(layout["selected_count"])
        self.index_path = root / "payload-index.jsonl"
        self.shards_path = root / "payload-shards.jsonl"
        self._check_ref(
            layout["payload_index"], self.index_path, "radjax_tome_payload_index_v2"
        )
        self._check_ref(
            layout["shard_index"],
            self.shards_path,
            "radjax_tome_payload_shard_index_v1",
        )
        self._index = iter(_lines(self.index_path))
        self._shards = iter(_lines(self.shards_path))
        self._overall = _SequenceDigest()
        self._selection = 0
        self._index_count = 0
        self._shard_count = 0
        self.last_observed = "", 0
        self._seen_tmp = tempfile.TemporaryDirectory(prefix="radjax-tome-v2-ids-")
        self._seen = sqlite3.connect(Path(self._seen_tmp.name) / "logical-ids.sqlite3")
        self._seen.execute("CREATE TABLE ids (logical_id TEXT PRIMARY KEY)")

    @staticmethod
    def _check_ref(ref: Any, path: Path, schema: str) -> None:
        if not isinstance(ref, dict):
            raise ContractError("shape_invalid")
        _require(
            ref, {"path", "sha256", "size_bytes", "record_count", "schema_version"}
        )
        if ref["schema_version"] != schema or _path(ref["path"]) != (
            "selected_exemplars/payload-index.jsonl"
            if schema.endswith("index_v2")
            else "selected_exemplars/payload-shards.jsonl"
        ):
            raise ContractError("payload_index_address_invalid")
        if _digest_path(path) != (
            _sha(ref["sha256"]),
            _nonnegative_int(ref["size_bytes"]),
        ):
            raise ContractError("digest_mismatch")

    def consume_shard(self, path: str, source: BinaryIO) -> Iterator[dict[str, Any]]:
        try:
            shard = next(self._shards)
        except StopIteration as exc:
            raise ContractError("manifest_record_count_mismatch") from exc
        self._shard_count += 1
        _require(
            shard,
            {
                "shard_id",
                "path",
                "sha256",
                "size_bytes",
                "first_selection_index",
                "last_selection_index",
                "record_count",
                "semantic_digest",
            },
        )
        shard_id = _nonnegative_int(shard["shard_id"])
        count = _nonnegative_int(shard["record_count"])
        first = _nonnegative_int(shard["first_selection_index"])
        last = _nonnegative_int(shard["last_selection_index"])
        if (
            shard_id != self._shard_count - 1
            or count < 1
            or count > self.capacity
            or first != self._selection
            or last != first + count - 1
            or _path(shard["path"]) != path
        ):
            raise ContractError("payload_index_address_invalid")
        digest = hashlib.sha256()
        size = 0
        shard_digest = _SequenceDigest()

        def records() -> Iterator[dict[str, Any]]:
            nonlocal size
            row_count = 0
            try:
                for raw_line in source:
                    digest.update(raw_line)
                    size += len(raw_line)
                    if not raw_line.strip():
                        raise ContractError("shape_invalid")
                    try:
                        payload = json.loads(raw_line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise ContractError("shape_invalid") from exc
                    if not isinstance(payload, dict) or row_count >= count:
                        raise ContractError("manifest_record_count_mismatch")
                    try:
                        index = next(self._index)
                    except StopIteration as exc:
                        raise ContractError("manifest_record_count_mismatch") from exc
                    self._index_count += 1
                    _require(
                        index,
                        {
                            "logical_id",
                            "selected_example_id",
                            "selected_position",
                            "selection_index",
                            "shard_id",
                            "row",
                            "payload_sha256",
                            "payload_semantic_digest",
                            "shard_sha256",
                        },
                    )
                    logical_id, semantic_digest = _semantic_record(payload)
                    if (
                        index.get("logical_id") != logical_id
                        or index.get("selected_example_id")
                        != payload["selected_example_id"]
                        or index.get("selected_position")
                        != payload["selected_position"]
                        or _nonnegative_int(index.get("selection_index"))
                        != self._selection
                        or _nonnegative_int(index.get("shard_id")) != shard_id
                        or _nonnegative_int(index.get("row")) != row_count
                        or _sha(index.get("payload_sha256")) != _canonical(payload)
                        or _sha(index.get("payload_semantic_digest")) != semantic_digest
                        or _sha(index.get("shard_sha256")) != _sha(shard["sha256"])
                    ):
                        raise ContractError("payload_index_address_invalid")
                    try:
                        self._seen.execute("INSERT INTO ids VALUES (?)", (logical_id,))
                    except sqlite3.IntegrityError as exc:
                        raise ContractError("payload_index_address_invalid") from exc
                    record = {
                        "logical_id": logical_id,
                        "payload_semantic_digest": semantic_digest,
                    }
                    shard_digest.add(record)
                    self._overall.add(record)
                    row_count += 1
                    self._selection += 1
                    yield payload
                if row_count != count:
                    raise ContractError("manifest_record_count_mismatch")
                observed = PREFIX + digest.hexdigest()
                if observed != _sha(shard["sha256"]) or size != _nonnegative_int(
                    shard["size_bytes"]
                ):
                    raise ContractError("digest_mismatch")
                self.last_observed = observed, size
                if shard_digest.finish() != _sha(shard["semantic_digest"]):
                    raise ContractError("payload_sequence_digest_mismatch")
            finally:
                # The enclosing reader owns final package state; this only
                # guarantees an early generator close cannot be marked valid.
                pass

        return records()

    def finish(self) -> None:
        try:
            next(self._index)
            raise ContractError("manifest_record_count_mismatch")
        except StopIteration:
            pass
        try:
            next(self._shards)
            raise ContractError("manifest_record_count_mismatch")
        except StopIteration:
            pass
        index_ref = self.layout["payload_index"]
        shard_ref = self.layout["shard_index"]
        if (
            self._index_count != _nonnegative_int(index_ref["record_count"])
            or self._shard_count != _nonnegative_int(shard_ref["record_count"])
            or self._selection != self.selected_count
        ):
            raise ContractError("manifest_record_count_mismatch")
        sequence = self._overall.finish()
        if sequence != _sha(self.layout["sequence_digest"]):
            raise ContractError("payload_sequence_digest_mismatch")
        if (
            self.selected_count != self.identity["selected_count"]
            or sequence != self.identity["payload_sequence_digest"]
        ):
            raise ContractError("payload_semantic_projection_invalid")
        self._seen.close()
        self._seen_tmp.cleanup()


class _ArchiveStreamingReader:
    """One-pass canonical archive reader; it never extracts package members."""

    def __init__(self, path: Path, *, strict: bool) -> None:
        self._path = path
        self._strict = strict
        self._warnings: list[str] = []
        self._state = "open"
        self._temp = tempfile.TemporaryDirectory(prefix="radjax-tome-v2-stream-")
        self._root = Path(self._temp.name)
        self._physical_transport, gzip_canonical = _archive_transport(path)
        if not gzip_canonical:
            self._warnings.append("transport_noncanonical")
        try:
            self._archive = tarfile.open(path, mode="r|*")
            self._members = iter(self._archive)
            self._prepare()
        except Exception:
            self.close(failed=True)
            raise

    @property
    def descriptor(self) -> StreamingTomeDescriptor:
        return self._descriptor

    @property
    def verification_state(self) -> str:
        return self._state

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self._warnings))

    def _next(self, expected: str | None = None) -> tuple[tarfile.TarInfo, BinaryIO]:
        try:
            member = next(self._members)
        except StopIteration as exc:
            raise ContractError("transport_corrupt") from exc
        name = _path(member.name)
        if expected is not None and name != expected:
            raise ContractError("ordering_invalid")
        if not _check_member_metadata(member):
            self._warnings.append("transport_noncanonical")
        source = self._archive.extractfile(member)
        if source is None:
            raise ContractError("transport_corrupt")
        return member, source

    def _prepare(self) -> None:
        _, source = self._next("cover_page.json")
        cover = _json_bytes(_read_small_member(source))
        _require(
            cover,
            {
                "schema_version",
                "identity",
                "training",
                "package",
                "manifests",
                "authority",
                "provenance",
                "validation",
            },
        )
        if cover["schema_version"] != "radjax_tome_cover_v4":
            raise ContractError("schema_version_unsupported")
        package = cover["package"]
        if (
            not isinstance(package, dict)
            or set(package) != {"profile", "transport"}
            or package.get("profile") not in PROFILES
            or package.get("transport") not in TRANSPORTS
        ):
            raise ContractError("profile_inventory_mismatch")
        if package["transport"] != self._physical_transport:
            raise ContractError("transport_mismatch")
        manifests = cover["manifests"]
        if not isinstance(manifests, dict) or set(manifests) != {"header"}:
            raise ContractError("shape_invalid")
        ref = manifests["header"]
        if not isinstance(ref, dict):
            raise ContractError("shape_invalid")
        _require(ref, {"path", "sha256", "size_bytes", "schema_version"})
        if (
            ref["schema_version"] != "tome_content_manifest_header_v3"
            or _path(ref["path"]) != "manifests/content-manifest-header.json"
        ):
            raise ContractError("shape_invalid")
        _, source = self._next("manifests/content-manifest-header.json")
        raw_header = _read_small_member(source)
        if (PREFIX + hashlib.sha256(raw_header).hexdigest(), len(raw_header)) != (
            _sha(ref["sha256"]),
            _nonnegative_int(ref["size_bytes"]),
        ):
            raise ContractError("digest_mismatch")
        header = _json_bytes(raw_header)
        _require(
            header,
            {
                "schema_version",
                "profile",
                "semantic_identity_digest",
                "inventory_path",
                "inventory_sha256",
                "inventory_size_bytes",
                "entry_count",
            },
        )
        if (
            header["schema_version"] != "tome_content_manifest_header_v3"
            or header["profile"] != package["profile"]
        ):
            raise ContractError("profile_inventory_mismatch")
        inventory_path = _path(header["inventory_path"])
        if inventory_path != "manifests/content-manifest-inventory.jsonl":
            raise ContractError("shape_invalid")
        _, source = self._next(inventory_path)
        inventory_file = self._root / "inventory.jsonl"
        if _copy_member_to_temp(source, inventory_file) != (
            _sha(header["inventory_sha256"]),
            _nonnegative_int(header["inventory_size_bytes"]),
        ):
            raise ContractError("digest_mismatch")
        identity = _validate_identity(cover["identity"])
        if (
            header["semantic_identity_digest"] != identity["semantic_digest"]
            or cover["training"] != identity["training_contract"]
            or cover["authority"] != identity["authority"]
        ):
            raise ContractError("payload_semantic_projection_invalid")
        self._inventory = _InventoryCursor(
            inventory_file,
            header_path="manifests/content-manifest-header.json",
            inventory_path=inventory_path,
        )
        self._inventory_count = _nonnegative_int(header["entry_count"])
        self._identity = identity
        self._layout: dict[str, Any] | None = None
        self._payload: _ArchivePayloadValidator | None = None
        self._descriptor = StreamingTomeDescriptor(
            package["profile"],
            self._physical_transport,
            identity,
            identity["selected_count"],
        )

    def __iter__(self) -> Iterator[dict[str, Any]]:
        if self._state != "open":
            return iter(())
        return self._records()

    def _records(self) -> Iterator[dict[str, Any]]:
        try:
            for member in self._members:
                name = _path(member.name)
                if not _check_member_metadata(member):
                    self._warnings.append("transport_noncanonical")
                entry = self._inventory.next()
                if entry["path"] != name:
                    raise ContractError("ordering_invalid")
                source = self._archive.extractfile(member)
                if source is None:
                    raise ContractError("transport_corrupt")
                if name == "selected_exemplars/payload-index.jsonl":
                    observed = _copy_member_to_temp(
                        source, self._root / "payload-index.jsonl"
                    )
                elif name == "selected_exemplars/payload-shards.jsonl":
                    observed = _copy_member_to_temp(
                        source, self._root / "payload-shards.jsonl"
                    )
                elif name == "selected_exemplars/payload-layout.json":
                    raw = _read_small_member(source)
                    observed = (PREFIX + hashlib.sha256(raw).hexdigest(), len(raw))
                    self._layout = _json_bytes(raw)
                elif name.startswith("selected_exemplars/shards/"):
                    if self._layout is None or self._payload is None:
                        if (
                            self._layout is None
                            or not (self._root / "payload-index.jsonl").is_file()
                            or not (self._root / "payload-shards.jsonl").is_file()
                        ):
                            raise ContractError("ordering_invalid")
                        self._payload = _ArchivePayloadValidator(
                            self._root, self._layout, self._identity
                        )
                    # consume_shard yields records while hashing the raw member.
                    yield from self._payload.consume_shard(name, source)
                    # The raw digest was checked inside consume_shard; a shard
                    # entry's inventory digest is deliberately identical.
                    observed = self._payload.last_observed
                else:
                    observed = _digest_stream(source)
                if observed != (entry["sha256"], _nonnegative_int(entry["size_bytes"])):
                    raise ContractError("digest_mismatch")
            self._inventory.finish(self._inventory_count)
            if self._payload is None:
                raise ContractError("profile_inventory_mismatch")
            self._payload.finish()
            if self._strict and self.warnings:
                raise ContractError("transport_noncanonical")
            self._state = "fully_verified"
        except (ContractError, OSError, tarfile.TarError):
            self.close(failed=True)
            raise
        finally:
            if self._state == "fully_verified":
                self.close(completed=True)

    def close(self, *, failed: bool = False, completed: bool = False) -> None:
        if (
            self._state == "closed_early"
            or self._state == "failed"
            or self._state == "fully_verified"
        ):
            if self._state == "fully_verified" and completed:
                pass
            else:
                return
        if failed:
            self._state = "failed"
        elif completed:
            self._state = "fully_verified"
        elif self._state == "open":
            self._state = "closed_early"
        try:
            self._archive.close()
        finally:
            self._temp.cleanup()


def open_streaming_tome(path: Path, *, strict: bool = False) -> StreamingTomeReader:
    """Open a direct sequential v4 archive reader without full extraction."""

    return StreamingTomeReader(path, strict=strict)


def validate_archive(path: Path, *, strict: bool = False) -> Result:
    """Validate an archive by draining the direct sequential reader."""

    try:
        with open_streaming_tome(path, strict=strict) as reader:
            for _ in reader:
                pass
            return Result(True, warnings=reader.warnings)
    except ContractError as exc:
        return Result(False, (exc.code,))
    except (OSError, tarfile.TarError):
        return Result(False, ("transport_corrupt",))


def validate_streaming_tome(path: Path, *, strict: bool = False) -> Result:
    """Validate an M7 directory or direct sequential tar/gzip transport.

    ``strict=False`` accepts safe noncanonical transport metadata with the
    documented ``transport_noncanonical`` warning.  Strict mode rejects it.
    """

    if path.is_dir():
        result = validate_directory(path)
        if result.ok and _directory_declares_non_directory(path):
            return Result(False, ("transport_mismatch",))
        return result
    return validate_archive(path, strict=strict)


def _directory_declares_non_directory(root: Path) -> bool:
    try:
        return (
            _json(root / "cover_page.json").get("package", {}).get("transport")
            != "directory"
        )
    except ContractError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    result = validate_streaming_tome(args.path)
    print(json.dumps(result.to_dict(), sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
