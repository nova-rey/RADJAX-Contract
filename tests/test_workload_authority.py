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
        "status": "pass",
        "workload_identity": "sha256:" + "0" * 64,
        "selected_sources": 253,
        "selected_coordinates": 253,
        "c1_c5_skipped": True,
        "full_teacher_pass_count": 0,
        "gpu_requested": False,
        "fallback": False,
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
        "checkpoint_manifest_digest": "sha256:" + "1" * 64,
        "source_row_closure_digest": "sha256:" + "2" * 64,
        "inventory_root": "sha256:" + "3" * 64,
        "finalization_identity": "sha256:" + "4" * 64,
        "benchmark_performed": False,
        "materialization_performed": False,
    }
    validate_finalization_receipt(receipt)
    with pytest.raises(ValueError):
        validate_finalization_receipt({**receipt, "benchmark_performed": True})
