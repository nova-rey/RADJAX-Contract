"""The private v3 journal state machine is closed and excluded from public use."""

import pytest

from radjax_contract.tome.v3.journal import validate_journal_state_v3
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
    with pytest.raises(ValueError, match="journal_state_invalid"):
        validate_journal_state_v3(_state(state="promoted"))
    with pytest.raises(ValueError, match="journal_commit_range_mismatch"):
        validate_journal_state_v3(_state(committed_next_selection_index=0))
