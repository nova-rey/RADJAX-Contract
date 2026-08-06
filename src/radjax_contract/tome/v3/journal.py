"""Pure v3 construction-journal validation; no producer filesystem actions."""

from __future__ import annotations

from collections.abc import Mapping

from radjax_contract.tome.v3.issues import TomeV3ValidationError, ValidationPhaseV3
from radjax_contract.tome.v3.models import JournalStateV3

_STATES = frozenset(
    {"OPEN", "SEALING", "COMPLETE_INTENT", "PROMOTING", "PROMOTED", "ABORTED"}
)


def validate_journal_state_v3(state: JournalStateV3) -> None:
    """Validate the state-machine facts which make resume fail closed.

    The journal remains producer-private.  This function deliberately has no
    path argument, no I/O, and no public-package return value.
    """

    if (
        not state.transaction_id
        or not state.configuration_identity
        or not state.semantic_authority_identity
    ):
        raise TomeV3ValidationError(
            "journal_binding_missing", phase=ValidationPhaseV3.DISCOVERY
        )
    if state.state not in _STATES:
        raise TomeV3ValidationError(
            "journal_state_invalid", phase=ValidationPhaseV3.DISCOVERY
        )
    expected = 0
    seen: set[str] = set()
    for receipt in state.sealed_shards:
        if not isinstance(receipt, Mapping):
            raise TomeV3ValidationError(
                "journal_receipt_invalid", phase=ValidationPhaseV3.DISCOVERY
            )
        required = {
            "shard_id",
            "member_path",
            "sha256",
            "size_bytes",
            "first_selection_index",
            "record_count",
        }
        if set(receipt) != required or receipt["shard_id"] in seen:
            raise TomeV3ValidationError(
                "journal_receipt_invalid", phase=ValidationPhaseV3.DISCOVERY
            )
        if (
            receipt["first_selection_index"] != expected
            or not isinstance(receipt["shard_id"], int)
            or not isinstance(receipt["record_count"], int)
            or receipt["record_count"] <= 0
            or not isinstance(receipt["member_path"], str)
            or not isinstance(receipt["size_bytes"], int)
            or receipt["size_bytes"] < 0
        ):
            raise TomeV3ValidationError(
                "journal_ranges_not_contiguous", phase=ValidationPhaseV3.DISCOVERY
            )
        seen.add(receipt["shard_id"])
        expected += receipt["record_count"]
    if state.committed_next_selection_index != expected:
        raise TomeV3ValidationError(
            "journal_commit_range_mismatch", phase=ValidationPhaseV3.DISCOVERY
        )
    if state.completion_intent and state.state not in {
        "COMPLETE_INTENT",
        "PROMOTING",
        "PROMOTED",
    }:
        raise TomeV3ValidationError(
            "journal_completion_state_invalid", phase=ValidationPhaseV3.DISCOVERY
        )
    if state.promotion_marker and state.state != "PROMOTED":
        raise TomeV3ValidationError(
            "journal_promotion_state_invalid", phase=ValidationPhaseV3.DISCOVERY
        )
