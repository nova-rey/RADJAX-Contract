from pathlib import Path

from tome_helpers import write_dense_tome

from radjax_contract.io import read_json, write_json
from radjax_contract.tome import (
    TomeCompression,
    TomeCompressionFamily,
    TomePayloadFormat,
    inspect_tome_for_consumption,
)


def test_inspect_valid_dense_tome_returns_dense_logits_plan(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")

    plan = inspect_tome_for_consumption(tome)

    assert plan.adapter_id == "dense_logits"
    assert plan.implemented is True
    assert plan.payload_format is TomePayloadFormat.DENSE_LOGITS_V0
    assert plan.compression is not None
    assert plan.compression.family is TomeCompressionFamily.NONE
    assert plan.blockers == ()


def test_inspect_future_legal_format_returns_adapter_but_unimplemented(
    tmp_path: Path,
) -> None:
    tome = write_dense_tome(
        tmp_path / "tome",
        payload_format=TomePayloadFormat.CASCADED_SOFT_LABELS_V1,
    )

    plan = inspect_tome_for_consumption(tome)

    assert plan.adapter_id == "cascaded_buckets"
    assert plan.implemented is False
    assert plan.payload_format is TomePayloadFormat.CASCADED_SOFT_LABELS_V1
    assert plan.blockers == ()


def test_inspect_illegal_payload_compression_returns_blocker(tmp_path: Path) -> None:
    tome = write_dense_tome(
        tmp_path / "tome",
        compression=TomeCompression(
            family=TomeCompressionFamily.CASCADED_BUCKETS,
            lossless=False,
            requires_reconstruction=True,
        ),
    )

    plan = inspect_tome_for_consumption(tome)

    assert plan.implemented is False
    assert any("compression_payload_mismatch" in item for item in plan.blockers)


def test_inspect_missing_cover_page_returns_blocker(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    (tome / "cover_page.json").unlink()

    plan = inspect_tome_for_consumption(tome)

    assert plan.implemented is False
    assert plan.adapter_id is None
    assert "cover_page_missing" in plan.blockers


def test_inspect_invalid_cover_page_returns_blocker(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    cover = read_json(tome / "cover_page.json")
    del cover["contents"]
    write_json(tome / "cover_page.json", cover)

    plan = inspect_tome_for_consumption(tome)

    assert plan.implemented is False
    assert any("cover_page_invalid" in item for item in plan.blockers)
