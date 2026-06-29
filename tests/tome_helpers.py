from __future__ import annotations

from pathlib import Path

import numpy as np

from radjax_contract.io import write_json, write_jsonl
from radjax_contract.tome import (
    TomeBehavioralSummary,
    TomeCompression,
    TomeCompressionFamily,
    TomeContentsSummary,
    TomeCorpusSource,
    TomeCorpusSummary,
    TomeCoverPage,
    TomeManifest,
    TomePayloadFormat,
    TomeRole,
    TomeSplitSummary,
    TomeStudentConsumptionSummary,
    TomeTeacherSummary,
)
from radjax_contract.tome.inspection import expected_adapter_for_payload
from radjax_contract.vocab import VocabContract


def write_dense_tome(
    path: Path,
    *,
    records: list[dict[str, object]] | None = None,
    logits: np.ndarray | None = None,
    vocab_size: int = 5,
    sequence_length: int = 3,
    payload_format: TomePayloadFormat = TomePayloadFormat.DENSE_LOGITS_V0,
    compression: TomeCompression | None = None,
) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    rows = records or [
        {"example_id": "example-0", "text": "alpha"},
        {"example_id": "example-1", "text": "beta"},
    ]
    values = (
        logits
        if logits is not None
        else np.ones((len(rows), sequence_length, vocab_size), dtype=np.float32)
    )
    compression = compression or _compression_for_payload(payload_format)
    write_jsonl(path / "records.jsonl", rows)
    np.save(path / "logits.npy", values, allow_pickle=False)
    manifest = TomeManifest(
        payload_format=payload_format,
        compression=compression,
        vocab_contract=VocabContract(tokenizer_id="toy", vocab_size=vocab_size),
        record_count=len(rows),
        sequence_length=sequence_length,
    )
    write_json(path / "manifest.json", manifest.to_dict())
    cover_page = TomeCoverPage(
        title="Tiny dense logits smoke Tome",
        description="Dense teacher-output Tome generated from tiny examples.",
        teacher=TomeTeacherSummary(
            teacher_id="fake-teacher",
            teacher_family="fake",
            backend="fake",
            teacher_dtype=str(values.dtype),
            teacher_vocab_size=vocab_size,
        ),
        corpus=TomeCorpusSummary(
            summary="Tiny synthetic smoke corpus.",
            sources=(
                TomeCorpusSource(
                    source_id="synthetic_smoke",
                    source_type="synthetic",
                    description="Small checked test fixture corpus.",
                    record_count=len(rows),
                ),
            ),
            contains_synthetic_examples=True,
        ),
        contents=TomeContentsSummary(
            role=TomeRole.TRAINING,
            record_count=len(rows),
            sequence_length=sequence_length,
            payload_format=payload_format,
            compression=compression,
        ),
        behavioral_fingerprint=TomeBehavioralSummary(),
        splits=TomeSplitSummary(split_role=TomeRole.TRAINING),
        student_consumption=TomeStudentConsumptionSummary(
            expected_adapter=expected_adapter_for_payload(payload_format),
            implemented_by_contract=payload_format is TomePayloadFormat.DENSE_LOGITS_V0,
            notes="Student may consume directly without reconstruction.",
        ),
    )
    write_json(path / "cover_page.json", cover_page.to_dict())
    return path


def _compression_for_payload(payload_format: TomePayloadFormat) -> TomeCompression:
    if payload_format is TomePayloadFormat.TOPK_WITH_TAIL_V0:
        return TomeCompression(
            family=TomeCompressionFamily.TOPK_WITH_TAIL,
            lossless=False,
            requires_reconstruction=True,
        )
    if payload_format is TomePayloadFormat.CASCADED_SOFT_LABELS_V1:
        return TomeCompression(
            family=TomeCompressionFamily.CASCADED_BUCKETS,
            lossless=False,
            requires_reconstruction=True,
        )
    if payload_format in {
        TomePayloadFormat.FINGERPRINT_CORRIDOR_V0,
        TomePayloadFormat.EXEMPLAR_RESERVOIR_V0,
    }:
        return TomeCompression(
            family=TomeCompressionFamily.BEHAVIORAL_FINGERPRINT,
            lossless=False,
            requires_reconstruction=True,
        )
    if payload_format is TomePayloadFormat.DYNAMIC_TOPK_CASCADED_BUCKETS_V0:
        return TomeCompression(
            family=TomeCompressionFamily.DYNAMIC_TOPK_CASCADED_BUCKETS,
            lossless=False,
            requires_reconstruction=True,
        )
    return TomeCompression()
