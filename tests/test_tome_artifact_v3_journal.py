"""The private v3 journal state machine is closed and excluded from public use."""

import pytest

from radjax_contract.tome.v3.journal import (
    journal_restart_disposition_v3,
    validate_journal_state_v3,
)
from radjax_contract.tome.v3.models import JournalStateV3


def _state(**changes: object) -> JournalStateV3:
    values: dict[str, object] = {
        "transaction_id": "run-1",
        "configuration_identity": "sha256:" + "1" * 64,
        "semantic_authority_identity": "sha256:" + "2" * 64,
        "state": "PROMOTED",
        "sealed_shards": (
            {
                "shard_id": 0,
                "member_path": "selected_exemplars/shards/shard-00000.jsonl",
                "sha256": "sha256:" + "3" * 64,
                "size_bytes": 1,
                "first_selection_index": 0,
                "record_count": 1,
            },
        ),
        "committed_next_selection_index": 1,
        "completion_intent": True,
        "promotion_marker": True,
    }
    values.update(changes)
    return JournalStateV3(**values)  # type: ignore[arg-type]


def test_journal_uses_published_state_vocabulary_and_contiguous_receipts() -> None:
    validate_journal_state_v3(_state())
    with pytest.raises(ValueError, match="producer_invalid_private_state"):
        validate_journal_state_v3(_state(state="promoted"))
    with pytest.raises(ValueError, match="producer_invalid_private_state"):
        validate_journal_state_v3(_state(committed_next_selection_index=0))


@pytest.mark.parametrize(
    ("case_id", "state", "public_present", "action", "visible"),
    [
        (
            "PC39",
            _state(
                state="OPEN",
                sealed_shards=(),
                committed_next_selection_index=0,
                completion_intent=False,
                promotion_marker=False,
            ),
            False,
            "resume_committed_prefix",
            False,
        ),
        (
            "PC42",
            _state(state="SEALING", completion_intent=False, promotion_marker=False),
            False,
            "resume_committed_prefix",
            False,
        ),
        (
            "PC43",
            _state(state="COMPLETE_INTENT", promotion_marker=False),
            False,
            "derive_public_evidence",
            False,
        ),
        (
            "PC44",
            _state(state="PROMOTING", promotion_marker=False),
            False,
            "retry_promotion",
            False,
        ),
        (
            "PC45",
            _state(state="PROMOTING", promotion_marker=False),
            True,
            "validate_public_then_mark",
            False,
        ),
        ("PC46", _state(), True, "open_completed_public_package", True),
    ],
)
def test_pc39_to_pc46_crash_snapshots_have_one_recovery_disposition(
    case_id: str,
    state: JournalStateV3,
    public_present: bool,
    action: str,
    visible: bool,
) -> None:
    """Each durable crash snapshot has an explicit, non-public recovery rule."""

    outcome = journal_restart_disposition_v3(
        state, public_location_present=public_present
    )
    assert outcome.action == action
    assert outcome.public_visible is visible


@pytest.mark.parametrize(
    ("case_id", "state", "kwargs"),
    [
        ("PC35", _state(), {"expected_configuration_identity": "sha256:" + "0" * 64}),
        (
            "PC36",
            _state(
                sealed_shards=(
                    _state().sealed_shards[0],
                    {
                        **_state().sealed_shards[0],
                        "shard_id": 0,
                        "first_selection_index": 1,
                    },
                ),
                committed_next_selection_index=2,
            ),
            {},
        ),
        (
            "PC37",
            _state(),
            {"expected_semantic_authority_identity": "sha256:" + "0" * 64},
        ),
        ("PC38", _state(), {"staged_member_paths": ("unreceipted.jsonl",)}),
        ("PC40", _state(), {"staged_member_paths": ("durable-without-receipt.jsonl",)}),
        ("PC41", _state(committed_next_selection_index=0), {}),
        ("PC47", _state(), {"expected_configuration_identity": "sha256:" + "0" * 64}),
    ],
)
def test_pc35_to_pc47_invalid_or_cross_bound_journal_states_refuse(
    case_id: str, state: JournalStateV3, kwargs: dict[str, object]
) -> None:
    """Private resume never accepts stale, mixed, or unreceipted state."""

    with pytest.raises(ValueError, match="producer_invalid_private_state"):
        journal_restart_disposition_v3(state, public_location_present=False, **kwargs)
