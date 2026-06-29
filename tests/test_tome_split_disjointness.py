from pathlib import Path

from tome_helpers import write_dense_tome

from radjax_contract.tome import validate_tome_split_disjointness


def test_three_disjoint_tome_splits_pass(tmp_path: Path) -> None:
    train = write_dense_tome(
        tmp_path / "train",
        records=[{"example_id": "train", "text": "a"}],
    )
    calibration = write_dense_tome(
        tmp_path / "calibration",
        records=[{"example_id": "calibration", "text": "b"}],
    )
    final_test = write_dense_tome(
        tmp_path / "final",
        records=[{"example_id": "final", "text": "c"}],
    )

    result = validate_tome_split_disjointness(train, calibration, final_test)

    assert result.ok is True


def test_overlapping_example_id_across_tome_splits_fails(tmp_path: Path) -> None:
    train = write_dense_tome(
        tmp_path / "train",
        records=[{"example_id": "shared", "text": "a"}],
    )
    calibration = write_dense_tome(
        tmp_path / "calibration",
        records=[{"example_id": "shared", "text": "b"}],
    )
    final_test = write_dense_tome(
        tmp_path / "final",
        records=[{"example_id": "final", "text": "c"}],
    )

    result = validate_tome_split_disjointness(train, calibration, final_test)

    assert result.ok is False
    assert any("example_id" in blocker for blocker in result.blockers)
