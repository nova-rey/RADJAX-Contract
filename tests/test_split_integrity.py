from radjax_contract.provenance import validate_three_way_split


def test_three_way_split_passes_disjoint_toy_manifests() -> None:
    result = validate_three_way_split(
        train=[_row("a")],
        calibration=[_row("b")],
        final_test=[_row("c")],
    )

    assert result.ok is True


def test_three_way_split_rejects_example_id_overlap() -> None:
    result = validate_three_way_split(
        train=[_row("a")],
        calibration=[_row("a")],
        final_test=[_row("c")],
    )

    assert result.ok is False
    assert "example_id overlap" in result.blockers[0]


def test_three_way_split_rejects_token_sequence_hash_overlap() -> None:
    result = validate_three_way_split(
        train=[_row("a", token_sequence_hash="shared")],
        calibration=[_row("b", token_sequence_hash="shared")],
        final_test=[_row("c")],
    )

    assert result.ok is False
    assert "token_sequence_hash overlap" in result.blockers[0]


def test_three_way_split_rejects_source_text_hash_overlap() -> None:
    result = validate_three_way_split(
        train=[_row("a", source_text_hash="shared")],
        calibration=[_row("b")],
        final_test=[_row("c", source_text_hash="shared")],
    )

    assert result.ok is False
    assert "source_text_hash overlap" in result.blockers[0]


def _row(
    example_id: str,
    *,
    token_sequence_hash: str | None = None,
    source_text_hash: str | None = None,
) -> dict[str, str]:
    return {
        "example_id": example_id,
        "token_sequence_hash": token_sequence_hash or f"tokens-{example_id}",
        "source_text_hash": source_text_hash or f"text-{example_id}",
    }
