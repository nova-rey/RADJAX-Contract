from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = (
    Path(__file__).parents[1]
    / "src/radjax_contract/contracts/radjax_tome/student_consumption/v1"
)


def _json(relative: str) -> object:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_c1_contract_asset_inventory_is_checksum_closed() -> None:
    expected = {}
    for line in (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", maxsplit=1)
        expected[relative] = digest
    observed = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in ROOT.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert expected == observed


def test_c1_contract_profile_and_schema_identifiers_are_closed() -> None:
    contract = _json("contract.json")
    profile = _json("profiles/native_v3_student_v1.json")
    assert contract == {
        "contract_id": "radjax_tome_student_consumption_contract",
        "publication_version": "1.0.0-draft",
        "schema_draft": "https://json-schema.org/draft/2020-12/schema",
        "native_artifact_family": "radjax_tome_cover_v3_student_consumption_v1",
        "profile_id": "native_v3_student_v1",
        "semantic_identity_schema": (
            "radjax_tome_student_consumption_semantic_identity_v1"
        ),
        "extension_policy": "closed_core_new_version_required",
        "canonicality_policy": "safe_noncanonical_transport_warns_strict_mode_rejects",
        "status": "normative_draft_pending_c1_review",
    }
    assert profile["requires_surfaces"] == ["corridor", "exemplar"]
    assert profile["role_authority"] == "role_and_instance_not_physical_path"
    assert set(profile["required_batch_roles"]) == {
        "target_shard",
        "example_registry",
        "corridor_mode_table",
        "corridor_assignment",
        "selected_passport_index",
        "selected_exemplar_payload",
    }


def test_c1_schemas_are_valid_and_profile_validates() -> None:
    schemas = sorted((ROOT / "schemas").glob("*.json"))
    assert schemas
    for path in schemas:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    profile_schema = _json("schemas/student_consumption_profile_v1.json")
    Draft202012Validator(profile_schema).validate(
        _json("profiles/native_v3_student_v1.json")
    )


def test_c1_fixture_declares_path_independent_role_bindings() -> None:
    fixture = _json("fixtures/valid/native_v3_student_v1.json")
    assert fixture["schema_version"] == "radjax_tome_student_consumption_manifest_v1"
    bindings = fixture["resources"]
    assert all(item["resource_id"] != item["inventory_binding"] for item in bindings)
    assert all("legacy/path" in item["training_payload_binding"] for item in bindings)
    assert fixture["semantic_identity"]["sequence"]["alignment"] == (
        "teacher_logit_position"
    )


def test_c1_issue_registry_has_complete_named_corpus_coverage() -> None:
    registry = _json("errors/issues_v1.json")
    adversarial = _json("fixtures/adversarial/cases.json")
    assert set(registry["codes"]) == set(adversarial["coverage"])
    assert registry["ordering"] == "phase_resource_id_code"
    assert registry["dependent_failure_policy"] == (
        "suppress_dependent_checks_accumulate_independent_checks"
    )
