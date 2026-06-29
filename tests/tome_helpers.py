from __future__ import annotations

from pathlib import Path

import numpy as np

from radjax_contract.io import write_json, write_jsonl
from radjax_contract.tome import TomeManifest, TomePayloadFormat
from radjax_contract.vocab import VocabContract


def write_dense_tome(
    path: Path,
    *,
    records: list[dict[str, object]] | None = None,
    logits: np.ndarray | None = None,
    vocab_size: int = 5,
    sequence_length: int = 3,
    payload_format: TomePayloadFormat = TomePayloadFormat.DENSE_LOGITS_V0,
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
    write_jsonl(path / "records.jsonl", rows)
    np.save(path / "logits.npy", values, allow_pickle=False)
    manifest = TomeManifest(
        payload_format=payload_format,
        vocab_contract=VocabContract(tokenizer_id="toy", vocab_size=vocab_size),
        record_count=len(rows),
        sequence_length=sequence_length,
    )
    write_json(path / "manifest.json", manifest.to_dict())
    return path
