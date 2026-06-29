from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from radjax_contract.artifacts.manifest import CONTRACT_PACKAGE
from radjax_contract.tome.manifest import TomeManifest
from radjax_contract.tome.payloads import (
    DEFAULT_DENSE_LOGITS_PAYLOAD,
    IMPLEMENTED_TOME_PAYLOAD_FORMATS,
    TomePayloadFormat,
    parse_tome_payload_format,
)
from radjax_contract.tome.records import TomeRecord, load_tome_records


@dataclass(frozen=True)
class TomeValidationResult:
    ok: bool
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    manifest: TomeManifest | None = None


def validate_tome(path: str | Path) -> TomeValidationResult:
    tome_dir = Path(path)
    blockers: list[str] = []
    warnings: list[str] = []
    manifest: TomeManifest | None = None
    if not tome_dir.exists():
        return TomeValidationResult(False, blockers=("tome_dir_missing",))
    if not tome_dir.is_dir():
        return TomeValidationResult(False, blockers=("tome_path_not_directory",))

    manifest_path = tome_dir / "manifest.json"
    if not manifest_path.exists():
        blockers.append("manifest_missing")
    else:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                blockers.append("manifest_not_object")
            else:
                manifest = TomeManifest.from_dict(payload)
        except json.JSONDecodeError as exc:
            blockers.append(f"manifest_malformed_json: {exc.msg}")
        except Exception as exc:
            blockers.append(f"manifest_invalid: {type(exc).__name__}: {exc}")

    records_result = load_tome_records(tome_dir / "records.jsonl")
    blockers.extend(records_result.blockers)
    warnings.extend(records_result.warnings)

    if manifest is not None:
        blockers.extend(_validate_manifest_fields(manifest))
        if (
            manifest.record_count is not None
            and len(records_result.records) != manifest.record_count
        ):
            blockers.append(
                "record_count_mismatch: "
                f"manifest={manifest.record_count} "
                f"records={len(records_result.records)}"
            )
        if manifest.payload_format not in IMPLEMENTED_TOME_PAYLOAD_FORMATS:
            blockers.append(
                f"payload_format_not_implemented: {manifest.payload_format.value}"
            )
        elif manifest.payload_format == TomePayloadFormat.DENSE_LOGITS_V0:
            blockers.extend(
                _validate_dense_logits_payload(
                    tome_dir,
                    manifest=manifest,
                    record_count=len(records_result.records),
                )
            )
        blockers.extend(_validate_shards(tome_dir, manifest))

    return TomeValidationResult(
        ok=not blockers,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        manifest=manifest,
    )


def validate_tome_split_disjointness(
    training_tome: str | Path,
    calibration_tome: str | Path,
    final_test_tome: str | Path,
) -> TomeValidationResult:
    tome_paths = {
        "training": Path(training_tome),
        "calibration": Path(calibration_tome),
        "final_test": Path(final_test_tome),
    }
    blockers: list[str] = []
    warnings: list[str] = []
    records_by_split: dict[str, tuple[TomeRecord, ...]] = {}
    for split_name, tome_path in tome_paths.items():
        result = validate_tome(tome_path)
        if not result.ok:
            blockers.extend(f"{split_name}: {blocker}" for blocker in result.blockers)
        warnings.extend(f"{split_name}: {warning}" for warning in result.warnings)
        records_by_split[split_name] = load_tome_records(
            tome_path / "records.jsonl"
        ).records
    blockers.extend(_split_overlap_blockers(records_by_split))
    return TomeValidationResult(
        ok=not blockers,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )


def _validate_manifest_fields(manifest: TomeManifest) -> tuple[str, ...]:
    blockers: list[str] = []
    if manifest.artifact_kind != "radjax_tome":
        blockers.append(f"artifact_kind_invalid: {manifest.artifact_kind}")
    if manifest.contract_package != CONTRACT_PACKAGE:
        blockers.append(f"contract_package_invalid: {manifest.contract_package}")
    if manifest.producer != "radjax-tome":
        blockers.append(f"producer_invalid: {manifest.producer}")
    if parse_tome_payload_format(manifest.payload_format.value) is None:
        blockers.append(f"payload_format_unknown: {manifest.payload_format}")
    if manifest.sequence_length is not None and manifest.sequence_length <= 0:
        blockers.append("sequence_length_must_be_positive")
    if manifest.vocab_contract is not None and manifest.vocab_contract.vocab_size <= 0:
        blockers.append("vocab_contract_vocab_size_must_be_positive")
    return tuple(blockers)


def _validate_dense_logits_payload(
    tome_dir: Path,
    *,
    manifest: TomeManifest,
    record_count: int,
) -> tuple[str, ...]:
    blockers: list[str] = []
    payload_path = tome_dir / str(
        manifest.metadata.get("payload_path", DEFAULT_DENSE_LOGITS_PAYLOAD)
    )
    if not payload_path.exists():
        return (f"payload_missing: {payload_path.name}",)
    try:
        logits = np.load(payload_path, allow_pickle=False)
    except Exception as exc:
        return (f"payload_unreadable: {type(exc).__name__}: {exc}",)
    if logits.ndim != 3:
        blockers.append(f"dense_logits_rank_invalid: rank={logits.ndim}")
        return tuple(blockers)
    if not np.issubdtype(logits.dtype, np.floating):
        blockers.append(f"dense_logits_dtype_not_float: {logits.dtype}")
    if not np.all(np.isfinite(logits)):
        blockers.append("dense_logits_nonfinite")
    if logits.shape[0] != record_count:
        blockers.append(
            f"dense_logits_record_dim_mismatch: logits={logits.shape[0]} "
            f"records={record_count}"
        )
    if (
        manifest.sequence_length is not None
        and logits.shape[1] != manifest.sequence_length
    ):
        blockers.append(
            f"dense_logits_sequence_dim_mismatch: logits={logits.shape[1]} "
            f"manifest={manifest.sequence_length}"
        )
    if (
        manifest.vocab_contract is not None
        and logits.shape[2] != manifest.vocab_contract.vocab_size
    ):
        blockers.append(
            f"dense_logits_vocab_dim_mismatch: logits={logits.shape[2]} "
            f"vocab={manifest.vocab_contract.vocab_size}"
        )
    return tuple(blockers)


def _validate_shards(tome_dir: Path, manifest: TomeManifest) -> tuple[str, ...]:
    blockers: list[str] = []
    if manifest.shards and manifest.shard_count != len(manifest.shards):
        blockers.append(
            f"shard_count_mismatch: shard_count={manifest.shard_count} "
            f"shards={len(manifest.shards)}"
        )
    for shard in manifest.shards:
        if not (tome_dir / shard.path).exists():
            blockers.append(f"shard_missing: {shard.path}")
    return tuple(blockers)


def _split_overlap_blockers(
    records_by_split: dict[str, tuple[TomeRecord, ...]],
) -> tuple[str, ...]:
    blockers: list[str] = []
    for key in ("example_id", "token_ids_sha256", "source_sha256", "text_sha256"):
        owners: dict[str, str] = {}
        for split_name, records in records_by_split.items():
            for record in records:
                value = record.identity_keys().get(key)
                if value is None:
                    continue
                previous = owners.get(value)
                if previous is not None and previous != split_name:
                    blockers.append(
                        f"tome_split_overlap {key} between {previous} "
                        f"and {split_name}: {value}"
                    )
                owners[value] = split_name
    return tuple(blockers)
