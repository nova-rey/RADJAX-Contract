"""Closed public contract for portable M8G replay workloads."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

SCHEMA_VERSION = "radjax_m8g_workload_v1"
_ROLES = {
    "source_row",
    "model_member",
    "corpus",
    "checkpoint",
    "authority",
    "provenance",
    "report",
    "selection",
    "teacher_inventory",
    "selected_source",
    "selected_coordinate",
    "finalization",
    "replay_preflight",
}
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise ValueError("workload path must be relative")
    p = PurePosixPath(value)
    if ".." in p.parts or p == PurePosixPath(".") or str(p) != value or "\\" in value:
        raise ValueError("workload path escapes bundle")
    return value


def inventory_root(entries: list[Mapping[str, Any]]) -> str:
    normalized = []
    seen: set[str] = set()
    folded: set[str] = set()
    for entry in entries:
        if set(entry) != {
            "path",
            "size_bytes",
            "sha256",
            "role",
            "semantic_identity",
            "schema_profile",
            "declaring_record",
            "reason",
        }:
            raise ValueError("inventory entry fields invalid")
        path = validate_relative_path(entry["path"])
        if path in seen or path.casefold() in folded:
            raise ValueError("duplicate workload inventory path")
        seen.add(path)
        folded.add(path.casefold())
        if type(entry["size_bytes"]) is not int or entry["size_bytes"] < 0:
            raise ValueError("inventory size invalid")
        if not isinstance(entry["sha256"], str) or not _DIGEST.fullmatch(
            entry["sha256"]
        ):
            raise ValueError("inventory digest invalid")
        if entry["role"] not in _ROLES:
            raise ValueError("inventory role invalid")
        normalized.append(dict(entry))
    normalized.sort(key=lambda x: x["path"])
    return digest(normalized)


def encode_workload_record(record: Mapping[str, Any]) -> bytes:
    """Canonical closed-record encoding used for every workload authority record."""
    if not isinstance(record, Mapping) or "schema_version" not in record:
        raise ValueError("workload record schema missing")
    if record["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported workload record schema")
    if "mode" in record:
        validate_replay_preflight(record)
    elif "finalization_identity" in record and "status" in record:
        validate_finalization_receipt(record)
    elif "model_root" in record:
        validate_teacher_inventory(record)
    return canonical_json_bytes(record) + b"\n"


def decode_workload_record(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("workload record must be an object")
    return value


def validate_source_row_closure(rows: list[Mapping[str, Any]]) -> None:
    if len(rows) != 1000 or {r.get("row_index") for r in rows} != set(range(1000)):
        raise ValueError("source-row closure count/index invalid")
    if (
        len({r.get("example_id") for r in rows}) != 1000
        or len({r.get("source_id") for r in rows}) != 1000
    ):
        raise ValueError("source-row closure identity invalid")
    for row in rows:
        required = {
            "row_index",
            "example_id",
            "source_id",
            "source_relative_path",
            "source_file_digest",
            "row_digest",
            "corpus_identity",
            "selected",
            "selected_coordinates",
        }
        if set(row) != required or not isinstance(row["selected_coordinates"], list):
            raise ValueError("source-row fields invalid")
        validate_relative_path(row["source_relative_path"])
        for key in ("source_file_digest", "row_digest", "corpus_identity"):
            if not isinstance(row[key], str) or not _DIGEST.fullmatch(row[key]):
                raise ValueError("source-row digest invalid")


def validate_teacher_inventory(inventory: Mapping[str, Any]) -> None:
    if set(inventory) != {
        "schema_version",
        "model_root",
        "provenance",
        "model_files",
        "identity",
    }:
        raise ValueError("teacher inventory fields invalid")
    if inventory["schema_version"] != SCHEMA_VERSION or not isinstance(
        inventory["model_files"], list
    ):
        raise ValueError("teacher inventory schema invalid")
    validate_relative_path(inventory["model_root"])
    validate_relative_path(inventory["provenance"])
    for entry in inventory["model_files"]:
        if (
            set(entry)
            != {
                "path",
                "size_bytes",
                "sha256",
                "role",
                "semantic_identity",
                "schema_profile",
                "declaring_record",
                "reason",
            }
            or entry.get("role") != "model_member"
        ):
            raise ValueError("teacher inventory role invalid")
    if not _DIGEST.fullmatch(inventory["identity"]):
        raise ValueError("teacher inventory identity invalid")


def validate_finalization_receipt(receipt: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "status",
        "raw_generation_root_inventory",
        "checkpoint_manifest_digest",
        "source_row_closure_digest",
        "inventory_root",
        "finalization_identity",
        "benchmark_performed",
        "materialization_performed",
    }
    if (
        set(receipt) != required
        or receipt["schema_version"] != SCHEMA_VERSION
        or receipt["status"] != "finalized"
    ):
        raise ValueError("finalization receipt fields invalid")
    for key in (
        "raw_generation_root_inventory",
        "checkpoint_manifest_digest",
        "source_row_closure_digest",
        "inventory_root",
        "finalization_identity",
    ):
        if not _DIGEST.fullmatch(receipt[key]):
            raise ValueError("finalization receipt digest invalid")
    if receipt["benchmark_performed"] or receipt["materialization_performed"]:
        raise ValueError("finalization receipt records prohibited work")


def validate_replay_preflight(result: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "mode",
        "status",
        "workload_identity",
        "selected_sources",
        "selected_coordinates",
        "c1_c5_skipped",
        "full_teacher_pass_count",
        "gpu_requested",
        "fallback",
    }
    if set(result) != required or result["schema_version"] != SCHEMA_VERSION:
        raise ValueError("replay preflight fields invalid")
    if result["mode"] not in {
        "legacy_padded_monolithic",
        "compact_k_monolithic",
        "compact_k_immutable_body",
    }:
        raise ValueError("replay mode invalid")
    if (
        result["status"] != "pass"
        or result["selected_sources"] != 253
        or result["selected_coordinates"] != 253
        or not result["c1_c5_skipped"]
        or result["full_teacher_pass_count"] != 0
        or result["gpu_requested"]
        or result["fallback"]
    ):
        raise ValueError("replay preflight failed")
    if not _DIGEST.fullmatch(result["workload_identity"]):
        raise ValueError("replay workload identity invalid")


def validate_workload_authority(authority: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "workload_identity",
        "tome_commit",
        "contract_commit",
        "corpus_identity",
        "teacher_identity",
        "selection_identity",
        "checkpoint_manifest_digest",
        "source_row_closure_digest",
        "inventory_root",
        "replay_identity",
        "finalization_identity",
        "provenance",
        "counts",
    }
    if set(authority) != required or authority["schema_version"] != SCHEMA_VERSION:
        raise ValueError("workload authority fields invalid")
    for key in (
        "workload_identity",
        "corpus_identity",
        "teacher_identity",
        "selection_identity",
        "checkpoint_manifest_digest",
        "source_row_closure_digest",
        "inventory_root",
        "replay_identity",
        "finalization_identity",
    ):
        if not isinstance(authority[key], str) or not _DIGEST.fullmatch(authority[key]):
            raise ValueError(f"workload authority digest invalid: {key}")
    if not re.fullmatch(r"[0-9a-f]{40}", authority["tome_commit"]) or not re.fullmatch(
        r"[0-9a-f]{40}", authority["contract_commit"]
    ):
        raise ValueError("workload authority commit invalid")
    if authority["provenance"] != "NEW_DETERMINISTIC_M8G_1K_WORKLOAD":
        raise ValueError("workload provenance invalid")
    counts = authority["counts"]
    if counts != {
        "sources": 1000,
        "examples": 1000,
        "selected_sources": 253,
        "selected_coordinates": 253,
        "budget": 256,
        "underfill_reason": "global_ranked_supply_exhaustion",
    }:
        raise ValueError("workload counts invalid")


def validate_checkpoint_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "inventory",
        "inventory_root",
        "selection_identity",
        "checkpoint_identity",
        "teacher_identity",
        "corpus_identity",
    }
    if set(manifest) != required or manifest["schema_version"] != SCHEMA_VERSION:
        raise ValueError("checkpoint manifest fields invalid")
    for key in (
        "inventory_root",
        "selection_identity",
        "checkpoint_identity",
        "teacher_identity",
        "corpus_identity",
    ):
        if not isinstance(manifest[key], str) or not _DIGEST.fullmatch(manifest[key]):
            raise ValueError(f"checkpoint digest invalid: {key}")
    if not isinstance(manifest["inventory"], list):
        raise ValueError("checkpoint inventory invalid")
    if inventory_root(manifest["inventory"]) != manifest["inventory_root"]:
        raise ValueError("checkpoint inventory root mismatch")
