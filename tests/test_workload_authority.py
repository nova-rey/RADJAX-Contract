import pytest

from radjax_contract.tome.workload import (
    decode_workload_record,
    encode_workload_record,
    inventory_root,
    validate_finalization_receipt,
    validate_relative_path,
    validate_replay_preflight,
)


def test_portable_inventory_rejects_bad_paths_and_digests() -> None:
    with pytest.raises(ValueError):
        validate_relative_path("../escape")
    with pytest.raises(ValueError):
        inventory_root(
            [
                {
                    "path": "x",
                    "size_bytes": 1,
                    "sha256": "sha256:x",
                    "role": "corpus",
                    "semantic_identity": None,
                    "schema_profile": None,
                    "declaring_record": "a",
                    "reason": "b",
                }
            ]
        )


def test_replay_preflight_is_closed_and_fail_closed() -> None:
    result = {
        "schema_version": "radjax_m8g_workload_v1",
        "mode": "legacy_padded_monolithic",
        "requested_mode": "legacy_padded_monolithic",
        "executed_mode": "legacy_padded_monolithic",
        "status": "pass",
        "workload_identity": "sha256:" + "0" * 64,
        "selection_identity": "sha256:" + "1" * 64,
        "selected_coordinate_identity": "sha256:" + "2" * 64,
        "selected_sources": 253,
        "selected_coordinates": 253,
        "c1_c5_skipped": True,
        "full_teacher_pass_count": 0,
        "gpu_requested": False,
        "fallback": False,
        "selected_delivery_status": "not_started",
        "materialization_performed": False,
        "publication_performed": False,
        "resume_identity": "sha256:" + "3" * 64,
    }
    validate_replay_preflight(result)
    encoded = encode_workload_record({**result, "record_type": "replay_preflight"})
    assert decode_workload_record(encoded)["mode"] == result["mode"]
    with pytest.raises(ValueError):
        encode_workload_record({**result, "unknown": 1})
    with pytest.raises(ValueError):
        validate_replay_preflight({**result, "fallback": True})


def test_finalization_rejects_benchmark_work() -> None:
    receipt = {
        "schema_version": "radjax_m8g_workload_v1",
        "status": "finalized",
        "raw_generation_root_inventory": "sha256:" + "0" * 64,
        "original_progress_digest": "sha256:" + "1" * 64,
        "validation_report_digest": "sha256:" + "2" * 64,
        "selection_checkpoint_digest": "sha256:" + "3" * 64,
        "checkpoint_manifest_digest": "sha256:" + "4" * 64,
        "source_row_closure_digest": "sha256:" + "5" * 64,
        "inventory_root": "sha256:" + "6" * 64,
        "finalization_identity": "sha256:" + "7" * 64,
        "tome_commit": "a" * 40,
        "contract_commit": "b" * 40,
        "configuration_identity": "sha256:" + "8" * 64,
        "transaction_identity": "sha256:" + "9" * 64,
        "benchmark_performed": False,
        "materialization_performed": False,
    }
    validate_finalization_receipt(receipt)
    with pytest.raises(ValueError):
        validate_finalization_receipt({**receipt, "benchmark_performed": True})


def test_checkpoint_binding_is_closed_and_tamper_evident() -> None:
    from radjax_contract.tome.workload import validate_checkpoint_manifest

    zero = "sha256:" + "0" * 64
    empty_root = inventory_root([])
    manifest = {
        "record_type": "checkpoint_manifest",
        "schema_version": "radjax_m8g_workload_v1",
        "inventory": [],
        "inventory_root": empty_root,
        "selection_identity": zero,
        "selection_config_identity": zero,
        "score_pass_identity": zero,
        "source_row_closure_digest": zero,
        "checkpoint_identity": zero,
        "teacher_identity": zero,
        "corpus_identity": zero,
        "workload_identity": zero,
    }
    validate_checkpoint_manifest(manifest)
    with pytest.raises(ValueError):
        validate_checkpoint_manifest(
            {**manifest, "inventory_root": "sha256:" + "1" * 64}
        )
    with pytest.raises(ValueError):
        validate_checkpoint_manifest({**manifest, "unexpected": True})
