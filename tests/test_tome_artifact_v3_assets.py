"""Release-candidate static v3 Contract assets agree with the FV3 codec."""

from __future__ import annotations

import json

from radjax_contract.tome.contract_publication import (
    TOME_ARTIFACT_V3_CONTRACT_PROFILE_ID,
    TOME_ARTIFACT_V3_CONTRACT_PUBLICATION_VERSION,
)
from radjax_contract.tome.v3.assets import asset_path, verify_asset_checksums
from radjax_contract.tome.v3.codec import (
    DOMAIN_LABELS,
    digest,
    record_sequence_digest,
    semantic_root,
)


def test_final_contract_assets_are_discoverable_and_checksum_pinned() -> None:
    assert TOME_ARTIFACT_V3_CONTRACT_PUBLICATION_VERSION == "3.0.0"
    assert (
        TOME_ARTIFACT_V3_CONTRACT_PROFILE_ID == "selected_exemplar_semantic_profile_v3"
    )
    verify_asset_checksums()
    assert asset_path("contract.json").is_file()


def test_all_final_vectors_recompute_from_committed_inputs() -> None:
    vectors = json.loads(
        asset_path("vectors/tome_provenance_v3_vectors.json").read_text()
    )
    for vector in vectors["normative_root_vectors"]:
        expected = vector["expected"]
        context = vector["semantic_context"]
        records = vector["ordered_records"]
        closed_records = [
            {key: value for key, value in record.items() if key != "selection_index"}
            for record in records
        ]
        assert (
            digest(DOMAIN_LABELS["semantic_authority"], context["authority"])
            == expected["authority_identity"]
        )
        assert (
            digest(DOMAIN_LABELS["behavioral_policy"], context["behavioral_policy"])
            == expected["policy_identity"]
        )
        assert (
            record_sequence_digest(
                closed_records,
                selection_indexes=[record["selection_index"] for record in records],
            )
            == expected["sequence_digest"]
        )
        assert semantic_root(expected["root_input"]) == expected["semantic_root"]
