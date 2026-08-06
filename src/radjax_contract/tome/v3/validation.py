"""Fail-closed standard validation and pre-yield v3 streaming reader."""

from __future__ import annotations

import hashlib
import re
import tarfile
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from radjax_contract.tome.v3.codec import (
    DOMAIN_LABELS,
    digest,
    logical_record_id,
    record_sequence_digest,
    semantic_root,
)
from radjax_contract.tome.v3.issues import TomeV3ValidationError, ValidationPhaseV3
from radjax_contract.tome.v3.models import StandardIntegrityReportV3
from radjax_contract.tome.v3.schema import (
    CONTRACT_VERSION,
    IDENTITY_SCHEMA_VERSION,
    SEMANTIC_PROFILE_ID,
    normalize_authority,
    normalize_policy,
    normalize_semantic_record,
)
from radjax_contract.tome.v3.strict_json import NumberLexeme, load_jsonl, loads

_FIXED = frozenset(
    {
        "cover_page.json",
        "manifests/content-manifest-header.json",
        "manifests/content-manifest-inventory.jsonl",
        "provenance/semantic-identity.json",
        "provenance/semantic-authority.json",
        "provenance/behavioral-policy.json",
        "provenance/capabilities.json",
        "selected_exemplars/layout.json",
        "selected_exemplars/payload-index.jsonl",
        "selected_exemplars/payload-shards.jsonl",
    }
)
_INVENTORY_EXCLUDES = frozenset(
    {
        "cover_page.json",
        "manifests/content-manifest-header.json",
        "manifests/content-manifest-inventory.jsonl",
    }
)
_MEMBER_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
_INVENTORY_CLASSIFICATIONS = frozenset(
    {
        "training_critical",
        "integrity_or_provenance",
        "diagnostic",
        "human_readable",
        "operational",
    }
)
_INVENTORY_ROLES = frozenset(
    {
        "semantic_identity",
        "semantic_authority",
        "behavioral_policy",
        "capabilities",
        "payload_layout",
        "payload_index",
        "payload_shard_index",
        "payload_shard",
    }
)
_ROLE_PATHS = {
    "semantic_identity": "provenance/semantic-identity.json",
    "semantic_authority": "provenance/semantic-authority.json",
    "behavioral_policy": "provenance/behavioral-policy.json",
    "capabilities": "provenance/capabilities.json",
    "payload_layout": "selected_exemplars/layout.json",
    "payload_index": "selected_exemplars/payload-index.jsonl",
    "payload_shard_index": "selected_exemplars/payload-shards.jsonl",
}
_SHARD_PATH_PREFIX = "selected_exemplars/shards/"


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _safe(relative: str) -> str:
    if (
        not isinstance(relative, str)
        or not _MEMBER_PATH.fullmatch(relative)
        or "\\" in relative
    ):
        raise TomeV3ValidationError(
            "member_path_unsafe", phase=ValidationPhaseV3.DISCOVERY
        )
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or pure.as_posix() != relative
        or any(part in {".", ".."} for part in pure.parts)
    ):
        raise TomeV3ValidationError(
            "member_path_unsafe", phase=ValidationPhaseV3.DISCOVERY
        )
    return relative


def _wire_int(
    value: Any, *, phase: ValidationPhaseV3, code: str, minimum: int = 0
) -> int:
    """Normalize a JSON integer lexeme for nonsemantic closed wire fields."""

    if isinstance(value, NumberLexeme):
        spelling = str(value)
        if (
            not spelling
            or spelling.startswith("+")
            or "." in spelling
            or "e" in spelling.lower()
        ):
            raise TomeV3ValidationError(code, phase=phase)
        try:
            value = int(spelling)
        except ValueError as exc:
            raise TomeV3ValidationError(code, phase=phase) from exc
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise TomeV3ValidationError(code, phase=phase)
    return value


def _discover(root: Path) -> dict[str, Path]:
    members: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if path.is_symlink() or not path.is_file():
            raise TomeV3ValidationError(
                "member_type_invalid", phase=ValidationPhaseV3.DISCOVERY
            )
        relative = _safe(path.relative_to(root).as_posix())
        if relative in members:
            raise TomeV3ValidationError(
                "member_duplicate", phase=ValidationPhaseV3.DISCOVERY, location=relative
            )
        members[relative] = path
    return members


def _load(path: Path, *, phase: ValidationPhaseV3) -> Mapping[str, Any]:
    value = loads(path.read_text(encoding="utf-8"), phase=phase)
    if not isinstance(value, Mapping):
        raise TomeV3ValidationError("json_object_required", phase=phase)
    return value


def _closed(
    value: Mapping[str, Any],
    required: set[str],
    *,
    phase: ValidationPhaseV3,
    code: str,
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    if set(value) - required - optional or required - set(value):
        raise TomeV3ValidationError(code, phase=phase)


def _reference(
    value: Any,
    *,
    phase: ValidationPhaseV3,
    index: bool = False,
    expected_schema_version: str | None = None,
) -> Mapping[str, Any]:
    fields = {"path", "sha256", "size_bytes", "schema_version"} | (
        {"record_count"} if index else set()
    )
    if not isinstance(value, Mapping):
        raise TomeV3ValidationError("reference_invalid", phase=phase)
    _closed(value, fields, phase=phase, code="reference_invalid")
    _safe(value["path"])
    if (
        not isinstance(value["sha256"], str)
        or not value["sha256"].startswith("sha256:")
        or not isinstance(value["schema_version"], str)
    ):
        raise TomeV3ValidationError("reference_invalid", phase=phase)
    if (
        expected_schema_version is not None
        and value["schema_version"] != expected_schema_version
    ):
        raise TomeV3ValidationError("reference_invalid", phase=phase)
    _wire_int(value["size_bytes"], phase=phase, code="reference_invalid")
    if index and (
        _wire_int(value["record_count"], phase=phase, code="reference_invalid") < 0
    ):
        raise TomeV3ValidationError("reference_invalid", phase=phase)
    return value


def _verify_ref(
    members: Mapping[str, Path],
    reference: Mapping[str, Any],
    *,
    phase: ValidationPhaseV3,
    missing_code: str = "referenced_member_missing",
) -> None:
    path = reference["path"]
    if path not in members:
        raise TomeV3ValidationError(missing_code, phase=phase, location=path)
    raw = members[path].read_bytes()
    if _sha(raw) != reference["sha256"] or len(raw) != _wire_int(
        reference["size_bytes"], phase=phase, code="reference_invalid"
    ):
        raise TomeV3ValidationError(
            "referenced_member_corrupt", phase=phase, location=path
        )


def _transport(
    artifact: Path,
) -> tuple[str, Path, tempfile.TemporaryDirectory[str] | None]:
    if artifact.is_dir():
        return "directory", artifact, None
    if artifact.is_file() and artifact.suffix in {".tgz", ".rtome"}:
        temporary = tempfile.TemporaryDirectory(prefix="radjax-tome-v3-")
        root = Path(temporary.name)
        try:
            with tarfile.open(artifact, "r:*") as archive:
                seen_members: set[str] = set()
                for member in archive.getmembers():
                    if not member.isfile() and not member.isdir():
                        raise TomeV3ValidationError(
                            "member_type_invalid", phase=ValidationPhaseV3.DISCOVERY
                        )
                    name = _safe(member.name)
                    if name in seen_members:
                        raise TomeV3ValidationError(
                            "member_duplicate",
                            phase=ValidationPhaseV3.DISCOVERY,
                            location=name,
                        )
                    seen_members.add(name)
                    if member.isdir():
                        continue
                    target = root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    handle = archive.extractfile(member)
                    if handle is None:
                        raise TomeV3ValidationError(
                            "transport_corrupt", phase=ValidationPhaseV3.DISCOVERY
                        )
                    target.write_bytes(handle.read())
        except (OSError, tarfile.TarError) as exc:
            temporary.cleanup()
            raise TomeV3ValidationError(
                "transport_corrupt", phase=ValidationPhaseV3.DISCOVERY
            ) from exc
        return "tgz" if artifact.suffix == ".tgz" else "rtome", root, temporary
    raise TomeV3ValidationError(
        "transport_unsupported", phase=ValidationPhaseV3.DISCOVERY
    )


def _validate_root(
    artifact: Path,
    root: Path,
    transport: str,
    *,
    strict_transport: bool,
    defer_shard_raw: bool = False,
) -> tuple[
    StandardIntegrityReportV3,
    list[tuple[Path, dict[str, Any]]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    members = _discover(root)
    if not _FIXED <= set(members):
        raise TomeV3ValidationError(
            "required_member_missing", phase=ValidationPhaseV3.DISCOVERY
        )
    cover = _load(members["cover_page.json"], phase=ValidationPhaseV3.DISPATCH)
    cover_fields = {
        "schema_version",
        "contract_version",
        "package",
        "capabilities_ref",
        "semantic_identity_ref",
        "semantic_authority_ref",
        "behavioral_policy_ref",
        "manifest_header_ref",
        "record_count",
        "shard_count",
    }
    _closed(cover, cover_fields, phase=ValidationPhaseV3.DISPATCH, code="cover_invalid")
    if (
        cover["schema_version"] != "radjax_tome_cover_v5"
        or cover["contract_version"] != CONTRACT_VERSION
    ):
        raise TomeV3ValidationError(
            "schema_version_unsupported", phase=ValidationPhaseV3.DISPATCH
        )
    if (
        not isinstance(cover["package"], Mapping)
        or set(cover["package"]) != {"profile_id", "transport"}
        or cover["package"]["profile_id"] != SEMANTIC_PROFILE_ID
        or cover["package"]["transport"] != transport
    ):
        raise TomeV3ValidationError(
            "package_dispatch_mismatch", phase=ValidationPhaseV3.DISPATCH
        )
    if strict_transport and transport == "directory":
        raise TomeV3ValidationError(
            "transport_strict_archive_required", phase=ValidationPhaseV3.DISPATCH
        )
    header_ref = _reference(
        cover["manifest_header_ref"],
        phase=ValidationPhaseV3.RAW_MEMBERS,
        expected_schema_version="tome_content_manifest_header_v4",
    )
    _verify_ref(
        members,
        header_ref,
        phase=ValidationPhaseV3.RAW_MEMBERS,
        missing_code="graph_reference_missing",
    )
    header = _load(members[header_ref["path"]], phase=ValidationPhaseV3.GRAPH)
    header_fields = {
        "schema_version",
        "contract_version",
        "profile_id",
        "capabilities_ref",
        "semantic_identity_ref",
        "layout_ref",
        "inventory_ref",
        "entry_count",
    }
    _closed(
        header,
        header_fields,
        phase=ValidationPhaseV3.GRAPH,
        code="manifest_header_invalid",
    )
    if (
        header["schema_version"] != "tome_content_manifest_header_v4"
        or header["contract_version"] != CONTRACT_VERSION
        or header["profile_id"] != SEMANTIC_PROFILE_ID
    ):
        raise TomeV3ValidationError(
            "manifest_header_binding_mismatch", phase=ValidationPhaseV3.GRAPH
        )
    inventory_ref = _reference(
        header["inventory_ref"],
        phase=ValidationPhaseV3.GRAPH,
        expected_schema_version="tome_content_manifest_inventory_v4",
    )
    _verify_ref(
        members,
        inventory_ref,
        phase=ValidationPhaseV3.GRAPH,
        missing_code="graph_reference_missing",
    )
    inventory_rows = load_jsonl(
        members[inventory_ref["path"]].read_bytes(), phase=ValidationPhaseV3.GRAPH
    )
    if len(inventory_rows) != _wire_int(
        header["entry_count"],
        phase=ValidationPhaseV3.GRAPH,
        code="inventory_count_mismatch",
    ):
        raise TomeV3ValidationError(
            "inventory_count_mismatch", phase=ValidationPhaseV3.GRAPH
        )
    declared: set[str] = set()
    for row in inventory_rows:
        if not isinstance(row, Mapping):
            raise TomeV3ValidationError(
                "inventory_row_invalid", phase=ValidationPhaseV3.GRAPH
            )
        _closed(
            row,
            {
                "path",
                "sha256",
                "size_bytes",
                "member_role",
                "classification",
                "required_for_standard_validation",
            },
            phase=ValidationPhaseV3.GRAPH,
            code="inventory_row_invalid",
        )
        if (
            row["classification"] not in _INVENTORY_CLASSIFICATIONS
            or row["member_role"] not in _INVENTORY_ROLES
            or not isinstance(row["required_for_standard_validation"], bool)
        ):
            raise TomeV3ValidationError(
                "inventory_row_invalid", phase=ValidationPhaseV3.GRAPH
            )
        path = _safe(row["path"])
        role = row["member_role"]
        if role == "payload_shard":
            if not path.startswith(_SHARD_PATH_PREFIX) or not path.endswith(".jsonl"):
                raise TomeV3ValidationError(
                    "inventory_public_member_invalid",
                    phase=ValidationPhaseV3.GRAPH,
                    location=path,
                )
        elif _ROLE_PATHS.get(role) != path:
            raise TomeV3ValidationError(
                "inventory_public_member_invalid",
                phase=ValidationPhaseV3.GRAPH,
                location=path,
            )
        if path in declared or path in _INVENTORY_EXCLUDES:
            raise TomeV3ValidationError(
                "inventory_duplicate_or_control_member",
                phase=ValidationPhaseV3.GRAPH,
                location=path,
            )
        declared.add(path)
        if path not in members:
            raise TomeV3ValidationError(
                "referenced_member_missing",
                phase=ValidationPhaseV3.RAW_MEMBERS,
                location=path,
            )
        if defer_shard_raw and row["member_role"] == "payload_shard":
            continue
        member_raw = members[path].read_bytes()
        if _sha(member_raw) != row["sha256"] or len(member_raw) != _wire_int(
            row["size_bytes"],
            phase=ValidationPhaseV3.GRAPH,
            code="inventory_row_invalid",
        ):
            raise TomeV3ValidationError(
                "shard_raw_mismatch"
                if row["member_role"] == "payload_shard"
                else "inventory_member_mismatch",
                phase=ValidationPhaseV3.GRAPH,
                location=path,
            )
    if declared != set(members) - _INVENTORY_EXCLUDES:
        raise TomeV3ValidationError(
            "inventory_not_closed", phase=ValidationPhaseV3.GRAPH
        )
    for name in (
        "capabilities_ref",
        "semantic_identity_ref",
        "semantic_authority_ref",
        "behavioral_policy_ref",
    ):
        _verify_ref(
            members,
            _reference(
                cover[name],
                phase=ValidationPhaseV3.GRAPH,
                expected_schema_version={
                    "capabilities_ref": "radjax_tome_capabilities_v1",
                    "semantic_identity_ref": IDENTITY_SCHEMA_VERSION,
                    "semantic_authority_ref": "radjax_tome_semantic_authority_v1",
                    "behavioral_policy_ref": "radjax_tome_behavioral_policy_v1",
                }[name],
            ),
            phase=ValidationPhaseV3.GRAPH,
            missing_code="graph_reference_missing",
        )
    for name in ("capabilities_ref", "semantic_identity_ref", "layout_ref"):
        _verify_ref(
            members,
            _reference(
                header[name],
                phase=ValidationPhaseV3.GRAPH,
                expected_schema_version={
                    "capabilities_ref": "radjax_tome_capabilities_v1",
                    "semantic_identity_ref": IDENTITY_SCHEMA_VERSION,
                    "layout_ref": "radjax_tome_payload_layout_v2",
                }[name],
            ),
            phase=ValidationPhaseV3.GRAPH,
            missing_code="graph_reference_missing",
        )
    if (
        header["capabilities_ref"] != cover["capabilities_ref"]
        or header["semantic_identity_ref"] != cover["semantic_identity_ref"]
    ):
        raise TomeV3ValidationError(
            "cover_header_reference_mismatch", phase=ValidationPhaseV3.GRAPH
        )
    capabilities = _load(
        members[cover["capabilities_ref"]["path"]], phase=ValidationPhaseV3.GRAPH
    )
    _closed(
        capabilities,
        {"schema_version", "required", "optional"},
        phase=ValidationPhaseV3.GRAPH,
        code="capabilities_invalid",
    )
    if (
        capabilities["schema_version"] != "radjax_tome_capabilities_v1"
        or not isinstance(capabilities["required"], list)
        or not isinstance(capabilities["optional"], list)
        or set(capabilities["required"])
        != {"standard_integrity_v3", "streaming_shard_receipts_v3"}
        or len(capabilities["required"]) != len(set(capabilities["required"]))
        or not all(isinstance(value, str) for value in capabilities["optional"])
        or len(capabilities["optional"]) != len(set(capabilities["optional"]))
        or set(capabilities["optional"]) & set(capabilities["required"])
    ):
        raise TomeV3ValidationError(
            "capabilities_invalid", phase=ValidationPhaseV3.GRAPH
        )
    identity = _load(
        members[cover["semantic_identity_ref"]["path"]],
        phase=ValidationPhaseV3.SEMANTIC_ROOT,
    )
    identity_fields = {
        "schema_version",
        "contract_version",
        "semantic_profile_id",
        "semantic_authority_identity",
        "behavioral_policy_identity",
        "record_count",
        "ordered_record_sequence_digest",
        "semantic_root",
    }
    _closed(
        identity,
        identity_fields,
        phase=ValidationPhaseV3.SEMANTIC_ROOT,
        code="semantic_identity_invalid",
    )
    if (
        identity["schema_version"] != IDENTITY_SCHEMA_VERSION
        or identity["contract_version"] != CONTRACT_VERSION
        or identity["semantic_profile_id"] != SEMANTIC_PROFILE_ID
    ):
        raise TomeV3ValidationError(
            "semantic_identity_binding_mismatch", phase=ValidationPhaseV3.SEMANTIC_ROOT
        )
    identity["record_count"] = _wire_int(
        identity["record_count"],
        phase=ValidationPhaseV3.SEMANTIC_ROOT,
        code="semantic_identity_invalid",
    )
    cover["record_count"] = _wire_int(
        cover["record_count"], phase=ValidationPhaseV3.INDEXES, code="cover_invalid"
    )
    cover["shard_count"] = _wire_int(
        cover["shard_count"], phase=ValidationPhaseV3.INDEXES, code="cover_invalid"
    )
    authority = normalize_authority(
        _load(
            members[cover["semantic_authority_ref"]["path"]],
            phase=ValidationPhaseV3.SEMANTIC_ROOT,
        )
    )
    policy = normalize_policy(
        _load(
            members[cover["behavioral_policy_ref"]["path"]],
            phase=ValidationPhaseV3.SEMANTIC_ROOT,
        )
    )
    if identity["semantic_authority_identity"] != digest(
        DOMAIN_LABELS["semantic_authority"], authority
    ):
        raise TomeV3ValidationError(
            "semantic_authority_identity_mismatch",
            phase=ValidationPhaseV3.SEMANTIC_ROOT,
        )
    if identity["behavioral_policy_identity"] != digest(
        DOMAIN_LABELS["behavioral_policy"], policy
    ):
        raise TomeV3ValidationError(
            "semantic_policy_identity_mismatch",
            phase=ValidationPhaseV3.SEMANTIC_ROOT,
        )
    layout = _load(
        members[header["layout_ref"]["path"]], phase=ValidationPhaseV3.INDEXES
    )
    layout_fields = {
        "schema_version",
        "semantic_identity_ref",
        "payload_index_ref",
        "shard_index_ref",
        "record_count",
        "shard_capacity",
    }
    _closed(
        layout, layout_fields, phase=ValidationPhaseV3.INDEXES, code="layout_invalid"
    )
    if layout["semantic_identity_ref"] != cover["semantic_identity_ref"]:
        raise TomeV3ValidationError(
            "layout_identity_reference_mismatch", phase=ValidationPhaseV3.INDEXES
        )
    layout["record_count"] = _wire_int(
        layout["record_count"], phase=ValidationPhaseV3.INDEXES, code="layout_invalid"
    )
    if (
        layout["schema_version"] != "radjax_tome_payload_layout_v2"
        or layout["record_count"] != identity["record_count"]
        or cover["record_count"] != identity["record_count"]
    ):
        raise TomeV3ValidationError(
            "layout_identity_mismatch", phase=ValidationPhaseV3.INDEXES
        )
    payload_ref = _reference(
        layout["payload_index_ref"],
        phase=ValidationPhaseV3.INDEXES,
        index=True,
        expected_schema_version="radjax_tome_payload_index_v3",
    )
    shards_ref = _reference(
        layout["shard_index_ref"],
        phase=ValidationPhaseV3.INDEXES,
        index=True,
        expected_schema_version="radjax_tome_payload_shard_index_v2",
    )
    _verify_ref(members, payload_ref, phase=ValidationPhaseV3.INDEXES)
    _verify_ref(members, shards_ref, phase=ValidationPhaseV3.INDEXES)
    payload_rows = load_jsonl(
        members[payload_ref["path"]].read_bytes(), phase=ValidationPhaseV3.INDEXES
    )
    if (
        len(payload_rows) != identity["record_count"]
        or _wire_int(
            payload_ref["record_count"],
            phase=ValidationPhaseV3.INDEXES,
            code="payload_index_count_mismatch",
        )
        != identity["record_count"]
    ):
        raise TomeV3ValidationError(
            "payload_index_count_mismatch", phase=ValidationPhaseV3.INDEXES
        )
    normalized_payload_rows: list[dict[str, Any]] = []
    for expected_index, row in enumerate(payload_rows):
        if not isinstance(row, Mapping):
            raise TomeV3ValidationError(
                "payload_index_row_invalid", phase=ValidationPhaseV3.INDEXES
            )
        _closed(
            row,
            {"logical_record_id", "selection_index", "shard_id", "row"},
            phase=ValidationPhaseV3.INDEXES,
            code="payload_index_row_invalid",
        )
        row["selection_index"] = _wire_int(
            row["selection_index"],
            phase=ValidationPhaseV3.INDEXES,
            code="payload_index_order_invalid",
        )
        row["row"] = _wire_int(
            row["row"],
            phase=ValidationPhaseV3.INDEXES,
            code="payload_index_order_invalid",
        )
        row["shard_id"] = _wire_int(
            row["shard_id"],
            phase=ValidationPhaseV3.INDEXES,
            code="payload_index_order_invalid",
        )
        if row["selection_index"] != expected_index or not isinstance(
            row["logical_record_id"], str
        ):
            raise TomeV3ValidationError(
                "payload_index_order_invalid", phase=ValidationPhaseV3.INDEXES
            )
        normalized_payload_rows.append(dict(row))
    shard_rows = load_jsonl(
        members[shards_ref["path"]].read_bytes(), phase=ValidationPhaseV3.INDEXES
    )
    shard_sources: list[tuple[Path, dict[str, Any]]] = []
    shard_member_paths: set[str] = set()
    expected_first = 0
    for expected_shard_id, row in enumerate(shard_rows):
        if not isinstance(row, Mapping):
            raise TomeV3ValidationError(
                "shard_receipt_invalid", phase=ValidationPhaseV3.INDEXES
            )
        _closed(
            row,
            {
                "shard_id",
                "path",
                "sha256",
                "size_bytes",
                "first_selection_index",
                "record_count",
            },
            phase=ValidationPhaseV3.INDEXES,
            code="shard_receipt_invalid",
        )
        row["shard_id"] = _wire_int(
            row["shard_id"],
            phase=ValidationPhaseV3.INDEXES,
            code="shard_receipt_invalid",
        )
        row["first_selection_index"] = _wire_int(
            row["first_selection_index"],
            phase=ValidationPhaseV3.INDEXES,
            code="shard_receipt_invalid",
        )
        row["record_count"] = _wire_int(
            row["record_count"],
            phase=ValidationPhaseV3.INDEXES,
            code="shard_receipt_invalid",
        )
        row["size_bytes"] = _wire_int(
            row["size_bytes"],
            phase=ValidationPhaseV3.INDEXES,
            code="shard_receipt_invalid",
        )
        if (
            row["shard_id"] != expected_shard_id
            or row["first_selection_index"] != expected_first
            or row["path"] not in members
        ):
            raise TomeV3ValidationError(
                "shard_range_or_path_mismatch", phase=ValidationPhaseV3.INDEXES
            )
        shard_member_paths.add(row["path"])
        if not defer_shard_raw:
            raw = members[row["path"]].read_bytes()
            if _sha(raw) != row["sha256"] or len(raw) != row["size_bytes"]:
                raise TomeV3ValidationError(
                    "shard_raw_mismatch",
                    phase=ValidationPhaseV3.GRAPH,
                    location=row["path"],
                )
        expected_first += row["record_count"]
        shard_sources.append((members[row["path"]], dict(row)))
    if (
        expected_first != identity["record_count"]
        or len(shard_rows) != cover["shard_count"]
    ):
        raise TomeV3ValidationError(
            "shard_count_or_range_mismatch", phase=ValidationPhaseV3.INDEXES
        )
    inventoried_shard_paths = {
        row["path"] for row in inventory_rows if row["member_role"] == "payload_shard"
    }
    if inventoried_shard_paths != shard_member_paths:
        raise TomeV3ValidationError(
            "shard_inventory_mismatch", phase=ValidationPhaseV3.INDEXES
        )
    if _wire_int(
        shards_ref["record_count"],
        phase=ValidationPhaseV3.INDEXES,
        code="shard_index_count_mismatch",
    ) != len(shard_rows):
        raise TomeV3ValidationError(
            "shard_index_count_mismatch", phase=ValidationPhaseV3.INDEXES
        )
    return (
        StandardIntegrityReportV3(
            artifact,
            transport,
            identity["semantic_root"],
            identity["record_count"],
            len(shard_rows),
        ),
        shard_sources,
        normalized_payload_rows,
        dict(identity),
    )


def validate_tome_artifact_v3(
    artifact: Path, *, strict_transport: bool = False
) -> StandardIntegrityReportV3:
    transport, root, temporary = _transport(Path(artifact))
    try:
        report, shards, payload_rows, identity = _validate_root(
            Path(artifact), root, transport, strict_transport=strict_transport
        )
        _validate_records(shards, payload_rows, identity)
        return report
    finally:
        if temporary is not None:
            temporary.cleanup()


def _validate_records(
    shards: list[tuple[Path, dict[str, Any]]],
    payload_rows: list[dict[str, Any]],
    identity: Mapping[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    logical_ids: set[str] = set()
    locations: dict[tuple[int, int], dict[str, Any]] = {
        (row["shard_id"], row["row"]): row for row in payload_rows
    }
    if len(locations) != len(payload_rows):
        raise TomeV3ValidationError(
            "payload_index_location_duplicate", phase=ValidationPhaseV3.INDEXES
        )
    selection_index = 0
    for path, shard in shards:
        rows = load_jsonl(path.read_bytes(), phase=ValidationPhaseV3.SEMANTIC_RECORDS)
        if len(rows) != shard["record_count"]:
            raise TomeV3ValidationError(
                "shard_record_count_mismatch",
                phase=ValidationPhaseV3.SEMANTIC_RECORDS,
                location=str(path),
            )
        for physical_row, row in enumerate(rows):
            record = normalize_semantic_record(row)
            logical_id = logical_record_id(record)
            if logical_id in logical_ids:
                raise TomeV3ValidationError(
                    "logical_record_duplicate", phase=ValidationPhaseV3.SEMANTIC_RECORDS
                )
            index_row = locations.get((shard["shard_id"], physical_row))
            if (
                index_row is None
                or index_row["selection_index"] != selection_index
                or index_row["logical_record_id"] != logical_id
            ):
                raise TomeV3ValidationError(
                    "payload_index_location_mismatch", phase=ValidationPhaseV3.INDEXES
                )
            logical_ids.add(logical_id)
            records.append(record)
            selection_index += 1
    sequence = record_sequence_digest(records)
    if sequence != identity["ordered_record_sequence_digest"]:
        raise TomeV3ValidationError(
            "semantic_sequence_mismatch", phase=ValidationPhaseV3.SEMANTIC_ROOT
        )
    root_input = {key: identity[key] for key in identity if key != "semantic_root"}
    if semantic_root(root_input) != identity["semantic_root"]:
        raise TomeV3ValidationError(
            "semantic_root_mismatch", phase=ValidationPhaseV3.SEMANTIC_ROOT
        )
    return records


class StreamingTomeV3Reader:
    """A reader which fully checks each shard before exposing any of its rows."""

    def __init__(self, artifact: Path, *, strict_transport: bool = False) -> None:
        self.artifact = Path(artifact)
        self.transport, self.root, self._temporary = _transport(self.artifact)
        try:
            self.report, self._shards, self._payload_rows, self.identity = (
                _validate_root(
                    self.artifact,
                    self.root,
                    self.transport,
                    strict_transport=strict_transport,
                    defer_shard_raw=True,
                )
            )
        except Exception:
            if self._temporary is not None:
                self._temporary.cleanup()
            raise

    def __iter__(self) -> Iterator[dict[str, Any]]:
        for path, shard in self._shards:
            raw = path.read_bytes()
            if _sha(raw) != shard["sha256"] or len(raw) != shard["size_bytes"]:
                raise TomeV3ValidationError(
                    "shard_raw_mismatch",
                    phase=ValidationPhaseV3.GRAPH,
                    location=str(path),
                )
            rows = [
                normalize_semantic_record(row)
                for row in load_jsonl(raw, phase=ValidationPhaseV3.SEMANTIC_RECORDS)
            ]
            if len(rows) != shard["record_count"]:
                raise TomeV3ValidationError(
                    "shard_record_count_mismatch",
                    phase=ValidationPhaseV3.SEMANTIC_RECORDS,
                )
            yield from rows

    def close(self) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def __enter__(self) -> StreamingTomeV3Reader:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def open_tome_artifact_v3(
    artifact: Path, *, strict_transport: bool = False
) -> StreamingTomeV3Reader:
    return StreamingTomeV3Reader(Path(artifact), strict_transport=strict_transport)


def compare_governed_tome_artifact_v3(
    artifact: Path, expected_input: Path, *, strict_transport: bool = False
):
    """Compare an internally valid artifact to caller-supplied governed evidence."""

    from radjax_contract.tome.v3.external import compare_governed_v3

    transport, root, temporary = _transport(Path(artifact))
    try:
        report, shards, payload_rows, identity = _validate_root(
            Path(artifact), root, transport, strict_transport=strict_transport
        )
        _validate_records(shards, payload_rows, identity)
        return compare_governed_v3(
            Path(artifact), report, Path(expected_input), identity
        )
    finally:
        if temporary is not None:
            temporary.cleanup()


def verify_external_tome_attestation_v3(
    artifact: Path,
    attestation: Path | None,
    *,
    requirement,
    evaluation_time_utc,
    strict_transport: bool = False,
):
    """Apply external attestation only after standard validation succeeds."""

    from radjax_contract.tome.v3.external import verify_attestation_v3

    transport, root, temporary = _transport(Path(artifact))
    try:
        report, shards, payload_rows, identity = _validate_root(
            Path(artifact), root, transport, strict_transport=strict_transport
        )
        _validate_records(shards, payload_rows, identity)
        return verify_attestation_v3(
            Path(artifact),
            report,
            identity,
            None if attestation is None else Path(attestation),
            requirement=requirement,
            evaluation_time_utc=evaluation_time_utc,
        )
    finally:
        if temporary is not None:
            temporary.cleanup()


def validate_external_archive_receipt_v3(archive: Path, receipt: Path):
    """Validate caller-supplied raw archive receipt without inspecting its contents."""

    from radjax_contract.tome.v3.external import validate_archive_receipt_v3

    return validate_archive_receipt_v3(Path(archive), Path(receipt))
