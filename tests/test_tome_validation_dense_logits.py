from pathlib import Path

import numpy as np
from tome_helpers import write_dense_tome

from radjax_contract.io import read_json, write_json
from radjax_contract.tome import TomePayloadFormat, validate_tome


def test_valid_minimal_dense_logits_tome_passes(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")

    result = validate_tome(tome)

    assert result.ok is True
    assert result.manifest is not None


def test_missing_manifest_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    (tome / "manifest.json").unlink()

    result = validate_tome(tome)

    assert result.ok is False
    assert "manifest_missing" in result.blockers


def test_missing_records_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    (tome / "records.jsonl").unlink()

    result = validate_tome(tome)

    assert result.ok is False
    assert "records_missing" in result.blockers


def test_missing_logits_payload_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    (tome / "logits.npy").unlink()

    result = validate_tome(tome)

    assert result.ok is False
    assert "payload_missing: logits.npy" in result.blockers


def test_logits_rank_mismatch_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(
        tmp_path / "tome",
        logits=np.ones((2, 3), dtype=np.float32),
    )

    result = validate_tome(tome)

    assert result.ok is False
    assert "dense_logits_rank_invalid: rank=2" in result.blockers


def test_logits_record_dimension_mismatch_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(
        tmp_path / "tome",
        logits=np.ones((1, 3, 5), dtype=np.float32),
    )

    result = validate_tome(tome)

    assert result.ok is False
    assert any("dense_logits_record_dim_mismatch" in item for item in result.blockers)


def test_logits_vocab_dimension_mismatch_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(
        tmp_path / "tome",
        logits=np.ones((2, 3, 6), dtype=np.float32),
        vocab_size=5,
    )

    result = validate_tome(tome)

    assert result.ok is False
    assert any("dense_logits_vocab_dim_mismatch" in item for item in result.blockers)


def test_unsupported_future_payload_format_fails_clearly(tmp_path: Path) -> None:
    tome = write_dense_tome(
        tmp_path / "tome",
        payload_format=TomePayloadFormat.CASCADED_SOFT_LABELS_V1,
    )

    result = validate_tome(tome)

    assert result.ok is False
    assert "payload_format_not_implemented: cascaded_soft_labels_v1" in result.blockers


def test_shard_metadata_must_reference_existing_files(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    manifest = read_json(tome / "manifest.json")
    manifest["shards"] = [{"path": "missing.npy"}]
    write_json(tome / "manifest.json", manifest)

    result = validate_tome(tome)

    assert result.ok is False
    assert "shard_missing: missing.npy" in result.blockers
