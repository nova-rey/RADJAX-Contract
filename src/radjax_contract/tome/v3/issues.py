"""Stable issue vocabulary for the unreleased Tome artifact Contract v3."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ValidationPhaseV3(IntEnum):
    DISCOVERY = 1
    DISPATCH = 2
    RAW_MEMBERS = 3
    GRAPH = 4
    INDEXES = 5
    SEMANTIC_RECORDS = 6
    SEMANTIC_ROOT = 7
    GOVERNED_COMPARISON = 8
    EXTERNAL_ATTESTATION = 9


_PUBLIC_ERROR_CODES = frozenset(
    {
        "unsupported_version",
        "malformed_schema",
        "malformed_jsonl",
        "malformed_reference",
        "undeclared_member",
        "missing_member",
        "corrupt_member",
        "corrupt_shard",
        "incoherent_package_graph",
        "index_incoherent",
        "semantic_profile_unknown_field",
        "semantic_profile_required_field_missing",
        "semantic_sequence_mismatch",
        "semantic_root_mismatch",
        "authority_mismatch",
        "policy_mismatch",
        "governed_expected_root_mismatch",
        "attestation_envelope_invalid",
        "attestation_binding_mismatch",
        "attestation_algorithm_unsupported",
        "attestation_not_external",
        "attestation_unavailable_required",
        "attestation_expired",
        "producer_invalid_private_state",
    }
)


def public_error_code_v3(internal_code: str) -> str:
    """Map implementation-local diagnostics to the published v3 error catalog.

    ``IssueV3.detail`` retains the local diagnostic, while callers receive only
    the closed machine code committed in ``errors/errors_v3.json``.
    """

    exact = {
        "schema_version_unsupported": "unsupported_version",
        "transport_unsupported": "unsupported_version",
        "jsonl_blank_line": "malformed_jsonl",
        "jsonl_cr_not_allowed": "malformed_jsonl",
        "jsonl_final_newline_required": "malformed_jsonl",
        "jsonl_object_required": "malformed_jsonl",
        "duplicate_json_key": "malformed_schema",
        "reference_invalid": "malformed_reference",
        "external_evidence_inside_artifact": "attestation_not_external",
        "external_evidence_unavailable": "attestation_unavailable_required",
        "external_attestation_unavailable": "attestation_unavailable_required",
        "external_attestation_envelope_invalid": "attestation_envelope_invalid",
        "external_attestation_binding_mismatch": "attestation_binding_mismatch",
        "external_attestation_mismatch": "attestation_binding_mismatch",
        "external_attestation_unsupported": "attestation_algorithm_unsupported",
        "external_attestation_expired": "attestation_expired",
        "governed_comparison_binding_mismatch": "governed_expected_root_mismatch",
        "governed_expected_root_mismatch": "governed_expected_root_mismatch",
        "member_path_unsafe": "undeclared_member",
        "member_duplicate": "undeclared_member",
        "member_type_invalid": "undeclared_member",
        "required_member_missing": "missing_member",
        "referenced_member_missing": "missing_member",
        "graph_reference_missing": "incoherent_package_graph",
        "inventory_not_closed": "undeclared_member",
        "referenced_member_corrupt": "corrupt_member",
        "inventory_member_mismatch": "corrupt_member",
        "inventory_public_member_invalid": "incoherent_package_graph",
        "shard_raw_mismatch": "corrupt_shard",
        "semantic_authority_identity_mismatch": "authority_mismatch",
        "semantic_policy_identity_mismatch": "policy_mismatch",
        "semantic_sequence_mismatch": "semantic_sequence_mismatch",
        "semantic_root_mismatch": "semantic_root_mismatch",
        "semantic_identity_binding_mismatch": "semantic_root_mismatch",
    }
    if internal_code in exact:
        return exact[internal_code]
    if internal_code.startswith("journal_"):
        return "producer_invalid_private_state"
    if (
        internal_code.startswith("payload_index")
        or internal_code.startswith("shard_")
        or internal_code.startswith("layout_")
        or internal_code.endswith("_count_mismatch")
    ):
        return "index_incoherent"
    if internal_code in {"logical_record_duplicate", "logical_record_id_mismatch"}:
        return "index_incoherent"
    if internal_code.startswith("semantic_"):
        return "semantic_profile_unknown_field"
    if internal_code.endswith("_reference_mismatch") or internal_code in {
        "cover_header_reference_mismatch",
        "manifest_header_binding_mismatch",
        "package_dispatch_mismatch",
        "capabilities_invalid",
        "inventory_duplicate_or_control_member",
        "inventory_row_invalid",
    }:
        return "incoherent_package_graph"
    return "malformed_schema"


@dataclass(frozen=True, order=True)
class IssueV3:
    """One deterministic v3 validation finding.

    Codes are intentionally stable machine values rather than exception prose.
    The tuple sort order makes reports reproducible across transports.
    """

    phase: ValidationPhaseV3
    code: str
    location: str = ""
    detail: str = ""


class TomeV3ValidationError(ValueError):
    """Raised by the fail-closed v3 decoder and validator."""

    def __init__(
        self, code: str, *, phase: ValidationPhaseV3, location: str = ""
    ) -> None:
        public_code = public_error_code_v3(code)
        self.issue = IssueV3(phase, public_code, location, detail=code)
        super().__init__(public_code if not location else f"{public_code}:{location}")
