from pathlib import Path

from tome_helpers import write_dense_tome

from radjax_contract.io import read_json, write_json
from radjax_contract.tome import (
    TomeBehavioralSummary,
    TomeCompression,
    TomeCompressionFamily,
    TomeContentsSummary,
    TomeCorpusSource,
    TomeCorpusSummary,
    TomeCoverPage,
    TomePayloadFormat,
    TomeRole,
    TomeSplitSummary,
    TomeStudentConsumptionSummary,
    TomeTeacherSummary,
    load_tome_cover_page,
    validate_tome,
)


def _minimal_cover_page() -> TomeCoverPage:
    return TomeCoverPage(
        title="Tiny dense logits smoke Tome",
        description="Dense teacher-output Tome generated from tiny examples.",
        teacher=TomeTeacherSummary(
            teacher_id="fake-teacher",
            teacher_family="fake",
            backend="fake",
            teacher_dtype="float32",
            teacher_vocab_size=8,
        ),
        corpus=TomeCorpusSummary(
            summary="Tiny synthetic smoke corpus.",
            sources=(
                TomeCorpusSource(
                    source_id="synthetic_smoke",
                    source_type="synthetic",
                    description="Small checked test fixture corpus.",
                    record_count=2,
                ),
            ),
            contains_synthetic_examples=True,
        ),
        contents=TomeContentsSummary(
            role=TomeRole.TRAINING,
            record_count=2,
            sequence_length=3,
            payload_format=TomePayloadFormat.DENSE_LOGITS_V0,
            compression=TomeCompression(),
        ),
        behavioral_fingerprint=TomeBehavioralSummary(),
        splits=TomeSplitSummary(split_role=TomeRole.TRAINING),
        student_consumption=TomeStudentConsumptionSummary(
            expected_adapter="dense_logits",
            implemented_by_contract=True,
            notes="Student may consume directly without reconstruction.",
        ),
    )


def test_cover_page_round_trips() -> None:
    cover_page = _minimal_cover_page()

    round_tripped = TomeCoverPage.from_dict(cover_page.to_dict())

    assert round_tripped == cover_page


def test_minimal_dense_cover_page_serializes_to_json_compatible_dict() -> None:
    payload = _minimal_cover_page().to_dict()

    assert payload["cover_page_kind"] == "radjax_tome_cover_page"
    assert payload["contents"]["compression"]["family"] == "none"
    assert payload["corpus"]["sources"][0]["source_type"] == "synthetic"


def test_missing_required_cover_section_fails_with_clear_blocker(
    tmp_path: Path,
) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    cover = read_json(tome / "cover_page.json")
    del cover["corpus"]
    write_json(tome / "cover_page.json", cover)

    result = load_tome_cover_page(tome)

    assert result.ok is False
    assert any("cover_page_invalid" in item for item in result.blockers)
    assert any("missing_required_sections: corpus" in item for item in result.blockers)


def test_missing_cover_page_fails_validation(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    (tome / "cover_page.json").unlink()

    result = validate_tome(tome)

    assert result.ok is False
    assert "cover_page_missing" in result.blockers


def test_malformed_cover_page_fails_validation(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    (tome / "cover_page.json").write_text("{ nope", encoding="utf-8")

    result = validate_tome(tome)

    assert result.ok is False
    assert any("cover_page_malformed_json" in item for item in result.blockers)


def test_cover_payload_format_mismatch_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    cover = read_json(tome / "cover_page.json")
    cover["contents"]["payload_format"] = "cascaded_soft_labels_v1"
    cover["contents"]["compression"]["family"] = "cascaded_buckets"
    cover["student_consumption"]["expected_adapter"] = "cascaded_buckets"
    write_json(tome / "cover_page.json", cover)

    result = validate_tome(tome)

    assert result.ok is False
    assert any("cover_payload_format_mismatch" in item for item in result.blockers)


def test_cover_role_mismatch_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    cover = read_json(tome / "cover_page.json")
    cover["contents"]["role"] = "calibration"
    cover["splits"]["split_role"] = "calibration"
    write_json(tome / "cover_page.json", cover)

    result = validate_tome(tome)

    assert result.ok is False
    assert any("cover_role_mismatch" in item for item in result.blockers)


def test_cover_record_count_mismatch_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    cover = read_json(tome / "cover_page.json")
    cover["contents"]["record_count"] = 999
    write_json(tome / "cover_page.json", cover)

    result = validate_tome(tome)

    assert result.ok is False
    assert any("cover_record_count_mismatch" in item for item in result.blockers)
    assert any(
        "cover_record_count_records_mismatch" in item for item in result.blockers
    )


def test_cover_sequence_length_mismatch_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    cover = read_json(tome / "cover_page.json")
    cover["contents"]["sequence_length"] = 999
    write_json(tome / "cover_page.json", cover)

    result = validate_tome(tome)

    assert result.ok is False
    assert any("cover_sequence_length_mismatch" in item for item in result.blockers)
    assert any(
        "cover_sequence_length_logits_mismatch" in item for item in result.blockers
    )


def test_dense_logits_with_none_compression_passes(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")

    result = validate_tome(tome)

    assert result.ok is True


def test_dense_logits_with_cascaded_compression_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(
        tmp_path / "tome",
        compression=TomeCompression(
            family=TomeCompressionFamily.CASCADED_BUCKETS,
            lossless=False,
            requires_reconstruction=True,
        ),
    )

    result = validate_tome(tome)

    assert result.ok is False
    assert any("compression_payload_mismatch" in item for item in result.blockers)


def test_future_legal_payload_compression_fails_as_not_implemented(
    tmp_path: Path,
) -> None:
    tome = write_dense_tome(
        tmp_path / "tome",
        payload_format=TomePayloadFormat.CASCADED_SOFT_LABELS_V1,
    )

    result = validate_tome(tome)

    assert result.ok is False
    assert "payload_format_not_implemented: cascaded_soft_labels_v1" in result.blockers
    assert not any("compression_payload_mismatch" in item for item in result.blockers)


def test_teacher_vocab_size_mismatch_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome", vocab_size=5)
    cover = read_json(tome / "cover_page.json")
    cover["teacher"]["teacher_vocab_size"] = 6
    write_json(tome / "cover_page.json", cover)

    result = validate_tome(tome)

    assert result.ok is False
    assert any("cover_teacher_vocab_size_mismatch" in item for item in result.blockers)
    assert any(
        "cover_teacher_vocab_size_logits_mismatch" in item for item in result.blockers
    )


def test_behavioral_false_with_modes_or_exemplars_fails(tmp_path: Path) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    cover = read_json(tome / "cover_page.json")
    cover["behavioral_fingerprint"]["mode_count"] = 1
    cover["behavioral_fingerprint"]["mode_ids"] = ["mode-a"]
    cover["behavioral_fingerprint"]["exemplar_count"] = 1
    write_json(tome / "cover_page.json", cover)

    result = validate_tome(tome)

    assert result.ok is False
    assert any(
        "cover_behavioral_included_false_mode_count_mismatch" in item
        for item in result.blockers
    )
    assert "cover_behavioral_included_false_mode_ids_nonempty" in result.blockers
    assert any(
        "cover_behavioral_included_false_exemplar_count_mismatch" in item
        for item in result.blockers
    )


def test_behavioral_true_with_mode_count_list_mismatch_fails(
    tmp_path: Path,
) -> None:
    tome = write_dense_tome(tmp_path / "tome")
    cover = read_json(tome / "cover_page.json")
    cover["behavioral_fingerprint"]["included"] = True
    cover["behavioral_fingerprint"]["mode_count"] = 2
    cover["behavioral_fingerprint"]["mode_ids"] = ["mode-a"]
    write_json(tome / "cover_page.json", cover)

    result = validate_tome(tome)

    assert result.ok is False
    assert any(
        "cover_behavioral_mode_ids_count_mismatch" in item for item in result.blockers
    )
