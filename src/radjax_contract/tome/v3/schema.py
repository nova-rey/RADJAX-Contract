"""Closed v3 semantic-profile and public-object decoders.

These functions deliberately produce ordinary frozen-by-convention mappings only
after lexical JSON has been normalized by the field selected type.  They are the
authority for v3's closed maps; JSON Schema documents the same contract but
cannot preserve duplicate keys or number lexemes by itself.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from radjax_contract.tome.v3.codec import I64_MAX, FV3Error, decimal_to_binary64
from radjax_contract.tome.v3.issues import TomeV3ValidationError, ValidationPhaseV3
from radjax_contract.tome.v3.strict_json import NumberLexeme

CONTRACT_VERSION = "radjax_tome_artifact_contract@3.0.0"
SEMANTIC_PROFILE_ID = "selected_exemplar_semantic_profile_v3"
IDENTITY_SCHEMA_VERSION = "radjax_tome_semantic_identity_v3"
AUTHORITY_SCHEMA_VERSION = "radjax_tome_semantic_authority_v1"
POLICY_SCHEMA_VERSION = "radjax_tome_behavioral_policy_v1"
RECORD_FIELDS = frozenset(
    {
        "selected_example_id",
        "selected_position",
        "selected_score",
        "score_selected_position_entropy",
        "score_top_token_id",
        "source_shard_id",
        "source_row",
        "source_position",
        "source_score",
        "source_top_token_id",
        "source_score_policy",
        "payload_ref",
        "selected_policy",
        "source_delivery_path",
        "top_token_ids",
        "top_log_probs",
        "top_probs",
        "top_selection_mask",
        "effective_top_k",
        "top_mass",
        "tail_mass",
        "bucket_masses",
        "teacher_entropy",
        "sequence_length",
        "vocab_size",
        "num_buckets",
        "dynamic_top_k",
        "dynamic_mass_threshold",
        "dynamic_top_k_max",
        "top_k_saturated",
        "long_tail_class",
        "long_tail_warnings",
        "effective_top_k_fraction_of_vocab",
        "semantic_tail_tag",
        "selected_board",
        "corridor_mode_id",
        "corridor_fingerprint_id",
        "corridor_assignment_status",
    }
)
INTEGER_FIELDS = frozenset(
    {
        "selected_position",
        "score_top_token_id",
        "source_shard_id",
        "source_row",
        "source_position",
        "source_top_token_id",
        "effective_top_k",
        "sequence_length",
        "vocab_size",
        "num_buckets",
        "dynamic_top_k_max",
    }
)
F64_FIELDS = frozenset(
    {
        "selected_score",
        "score_selected_position_entropy",
        "source_score",
        "top_mass",
        "tail_mass",
        "teacher_entropy",
        "dynamic_mass_threshold",
        "effective_top_k_fraction_of_vocab",
    }
)
TEXT_FIELDS = frozenset(
    {
        "selected_example_id",
        "source_score_policy",
        "selected_policy",
        "source_delivery_path",
        "long_tail_class",
        "semantic_tail_tag",
        "selected_board",
        "corridor_mode_id",
        "corridor_fingerprint_id",
        "corridor_assignment_status",
    }
)
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
JSON_INTEGER = re.compile(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)\Z")


def _error(code: str, *, phase: ValidationPhaseV3) -> None:
    raise TomeV3ValidationError(code, phase=phase)


def _closed(
    value: Any,
    fields: set[str] | frozenset[str],
    *,
    phase: ValidationPhaseV3,
    code: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _error(f"{code}_not_object", phase=phase)
    actual = set(value)
    if actual - fields:
        _error(f"{code}_unknown_field", phase=phase)
    if fields - actual:
        _error(f"{code}_required_field_missing", phase=phase)
    return value


def _text(value: Any, *, phase: ValidationPhaseV3, code: str) -> str:
    if not isinstance(value, str) or not value:
        _error(code, phase=phase)
    if "\x00" in value or "\r" in value or "\n" in value:
        _error(code, phase=phase)
    return value


def _i64(value: Any, *, phase: ValidationPhaseV3, code: str, minimum: int = 0) -> int:
    lexeme = str(value) if isinstance(value, NumberLexeme) else None
    if lexeme is not None:
        if not JSON_INTEGER.fullmatch(lexeme):
            _error(code, phase=phase)
        result = int(lexeme)
    elif isinstance(value, int) and not isinstance(value, bool):
        result = value
    else:
        _error(code, phase=phase)
    if result < minimum or result > I64_MAX:
        _error(code, phase=phase)
    return result


def _f64(
    value: Any, *, phase: ValidationPhaseV3, code: str, unit_interval: bool = False
) -> float:
    try:
        result = (
            decimal_to_binary64(str(value))
            if isinstance(value, NumberLexeme)
            else float(value)
        )
    except (FV3Error, TypeError, ValueError):
        _error(code, phase=phase)
    if (
        result != result
        or result in (float("inf"), float("-inf"))
        or (result == 0 and str(value).startswith("-"))
    ):
        _error(code, phase=phase)
    if unit_interval and not 0 <= result <= 1:
        _error(code, phase=phase)
    return result


def _list(value: Any, *, phase: ValidationPhaseV3, code: str) -> Sequence[Any]:
    if not isinstance(value, list):
        _error(code, phase=phase)
    return value


def _digest(value: Any, *, phase: ValidationPhaseV3, code: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        _error(code, phase=phase)
    return value


def normalize_semantic_record(value: Any) -> dict[str, Any]:
    """Return one closed, typed selected-exemplar semantic record."""

    phase = ValidationPhaseV3.SEMANTIC_RECORDS
    record = _closed(value, RECORD_FIELDS, phase=phase, code="semantic_record")
    result: dict[str, Any] = {}
    for name in TEXT_FIELDS:
        result[name] = _text(record[name], phase=phase, code=f"{name}_invalid")
    for name in INTEGER_FIELDS:
        minimum = (
            1 if name in {"effective_top_k", "sequence_length", "vocab_size"} else 0
        )
        result[name] = _i64(
            record[name], phase=phase, code=f"{name}_invalid", minimum=minimum
        )
    for name in F64_FIELDS:
        result[name] = _f64(
            record[name],
            phase=phase,
            code=f"{name}_invalid",
            unit_interval=name
            in {
                "top_mass",
                "tail_mass",
                "dynamic_mass_threshold",
                "effective_top_k_fraction_of_vocab",
            },
        )
    result["top_token_ids"] = [
        _i64(item, phase=phase, code="top_token_id_invalid")
        for item in _list(
            record["top_token_ids"], phase=phase, code="top_token_ids_invalid"
        )
    ]
    result["top_log_probs"] = [
        _f64(item, phase=phase, code="top_log_prob_invalid")
        for item in _list(
            record["top_log_probs"], phase=phase, code="top_log_probs_invalid"
        )
    ]
    result["top_probs"] = [
        _f64(item, phase=phase, code="top_prob_invalid", unit_interval=True)
        for item in _list(record["top_probs"], phase=phase, code="top_probs_invalid")
    ]
    result["top_selection_mask"] = list(
        _list(
            record["top_selection_mask"], phase=phase, code="top_selection_mask_invalid"
        )
    )
    if not all(isinstance(item, bool) for item in result["top_selection_mask"]):
        _error("top_selection_mask_invalid", phase=phase)
    result["bucket_masses"] = [
        _f64(item, phase=phase, code="bucket_mass_invalid", unit_interval=True)
        for item in _list(
            record["bucket_masses"], phase=phase, code="bucket_masses_invalid"
        )
    ]
    result["long_tail_warnings"] = [
        _text(item, phase=phase, code="long_tail_warning_invalid")
        for item in _list(
            record["long_tail_warnings"], phase=phase, code="long_tail_warnings_invalid"
        )
    ]
    if not isinstance(record["top_k_saturated"], bool):
        _error("top_k_saturated_invalid", phase=phase)
    result["top_k_saturated"] = record["top_k_saturated"]
    result["payload_ref"] = normalize_payload_ref(record["payload_ref"])
    result["dynamic_top_k"] = normalize_dynamic_top_k(record["dynamic_top_k"], result)
    expected = result["effective_top_k"]
    if any(
        len(result[name]) != expected
        for name in (
            "top_token_ids",
            "top_log_probs",
            "top_probs",
            "top_selection_mask",
        )
    ):
        _error("effective_top_k_length_mismatch", phase=phase)
    if (
        len(result["bucket_masses"]) != result["num_buckets"]
        or result["effective_top_k"] > result["vocab_size"]
    ):
        _error("semantic_record_cross_field_mismatch", phase=phase)
    if (
        any(token >= result["vocab_size"] for token in result["top_token_ids"])
        or result["source_top_token_id"] != result["top_token_ids"][0]
    ):
        _error("semantic_record_token_mismatch", phase=phase)
    if (
        result["selected_position"] >= result["sequence_length"]
        or result["source_position"] >= result["sequence_length"]
    ):
        _error("semantic_record_position_mismatch", phase=phase)
    return {
        name: result[name]
        for name in sorted(RECORD_FIELDS, key=lambda item: item.encode())
    }


def normalize_payload_ref(value: Any) -> dict[str, Any]:
    phase = ValidationPhaseV3.SEMANTIC_RECORDS
    fields = {"kind", "source_shard_id", "source_row", "source_position"}
    result = _closed(value, fields, phase=phase, code="payload_ref")
    if result["kind"] != "source_coordinate":
        _error("payload_ref_kind_invalid", phase=phase)
    return {
        "kind": "source_coordinate",
        **{
            name: _i64(result[name], phase=phase, code=f"payload_ref_{name}_invalid")
            for name in fields - {"kind"}
        },
    }


def normalize_dynamic_top_k(value: Any, outer: Mapping[str, Any]) -> dict[str, Any]:
    phase = ValidationPhaseV3.SEMANTIC_RECORDS
    if not isinstance(value, Mapping) or not isinstance(value.get("kind"), str):
        _error("dynamic_top_k_invalid", phase=phase)
    if value["kind"] == "disabled_v1":
        _closed(value, {"kind"}, phase=phase, code="dynamic_top_k")
        if (
            outer["dynamic_mass_threshold"] != 0
            or outer["dynamic_top_k_max"] != 0
            or outer["top_k_saturated"]
        ):
            _error("dynamic_top_k_outer_mismatch", phase=phase)
        return {"kind": "disabled_v1"}
    if value["kind"] == "mass_threshold":
        payload = _closed(
            value, {"kind", "threshold", "max_k"}, phase=phase, code="dynamic_top_k"
        )
        threshold = _f64(
            payload["threshold"],
            phase=phase,
            code="dynamic_top_k_threshold_invalid",
            unit_interval=True,
        )
        max_k = _i64(
            payload["max_k"], phase=phase, code="dynamic_top_k_max_k_invalid", minimum=1
        )
        if (
            threshold != outer["dynamic_mass_threshold"]
            or max_k != outer["dynamic_top_k_max"]
        ):
            _error("dynamic_top_k_outer_mismatch", phase=phase)
        return {"kind": "mass_threshold", "threshold": threshold, "max_k": max_k}
    _error("dynamic_top_k_kind_invalid", phase=phase)


def normalize_authority(value: Any) -> dict[str, Any]:
    phase = ValidationPhaseV3.SEMANTIC_ROOT
    fields = {"schema_version", "contract_version", "semantic_profile_id", "entries"}
    obj = _closed(value, fields, phase=phase, code="semantic_authority")
    if (
        obj["schema_version"] != AUTHORITY_SCHEMA_VERSION
        or obj["contract_version"] != CONTRACT_VERSION
        or obj["semantic_profile_id"] != SEMANTIC_PROFILE_ID
    ):
        _error("semantic_authority_binding_mismatch", phase=phase)
    roles = [
        "corpus",
        "delivery",
        "score_pass",
        "selection",
        "teacher",
        "tokenizer_vocabulary",
    ]
    entries = _list(
        obj["entries"], phase=phase, code="semantic_authority_entries_invalid"
    )
    if len(entries) != len(roles):
        _error("semantic_authority_roles_invalid", phase=phase)
    normalized = []
    for entry in entries:
        closed = _closed(
            entry,
            {"role", "schema_id", "identity"},
            phase=phase,
            code="semantic_authority_entry",
        )
        normalized.append(
            {
                "role": _text(
                    closed["role"], phase=phase, code="semantic_authority_role_invalid"
                ),
                "schema_id": _text(
                    closed["schema_id"],
                    phase=phase,
                    code="semantic_authority_schema_invalid",
                ),
                "identity": _digest(
                    closed["identity"],
                    phase=phase,
                    code="semantic_authority_digest_invalid",
                ),
            }
        )
    if [entry["role"] for entry in normalized] != roles:
        _error("semantic_authority_roles_invalid", phase=phase)
    return {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "semantic_profile_id": SEMANTIC_PROFILE_ID,
        "entries": normalized,
    }


def normalize_policy(value: Any) -> dict[str, Any]:
    phase = ValidationPhaseV3.SEMANTIC_ROOT
    fields = {
        "schema_version",
        "contract_version",
        "semantic_profile_id",
        "selection_policy",
        "dynamic_top_k_policy",
        "corridor_link_policy",
    }
    obj = _closed(value, fields, phase=phase, code="behavioral_policy")
    if (
        obj["schema_version"] != POLICY_SCHEMA_VERSION
        or obj["contract_version"] != CONTRACT_VERSION
        or obj["semantic_profile_id"] != SEMANTIC_PROFILE_ID
    ):
        _error("behavioral_policy_binding_mismatch", phase=phase)
    return {
        name: (
            obj[name]
            if name in {"schema_version", "contract_version", "semantic_profile_id"}
            else _text(obj[name], phase=phase, code=f"behavioral_policy_{name}_invalid")
        )
        for name in sorted(fields, key=lambda item: item.encode())
    }
