from pathlib import Path

from radjax_contract.tome.records import load_tome_records


def test_records_accept_text_only_with_warning(tmp_path: Path) -> None:
    records = tmp_path / "records.jsonl"
    records.write_text('{"text":"hello"}\n', encoding="utf-8")

    result = load_tome_records(records)

    assert result.blockers == ()
    assert result.records[0].stable_identity() is not None
    assert result.warnings == ("record_missing_example_id line=1",)


def test_records_malformed_line_reports_line_number(tmp_path: Path) -> None:
    records = tmp_path / "records.jsonl"
    records.write_text('{"example_id":"a"}\n{bad\n', encoding="utf-8")

    result = load_tome_records(records)

    assert result.blockers
    assert "line=2" in result.blockers[0]


def test_records_duplicate_example_id_is_blocker(tmp_path: Path) -> None:
    records = tmp_path / "records.jsonl"
    records.write_text(
        '{"example_id":"a"}\n{"example_id":"a"}\n',
        encoding="utf-8",
    )

    result = load_tome_records(records)

    assert "record_duplicate_example_id a" in result.blockers
