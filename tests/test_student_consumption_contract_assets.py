from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

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
    assert profile["required_resource_encodings"] == {
        "target_shard": "npz",
        "corridor_assignment": "npz",
        "corridor_observed_statistics": "npz",
    }
    assert set(profile["required_batch_roles"]) == {
        "target_shard",
        "example_registry",
        "corridor_mode_table",
        "corridor_assignment",
        "selected_passport_index",
        "selected_exemplar_payload",
    }
    assert set(profile["required_validation_roles"]) == {
        "corridor_observed_statistics",
        "row_range_declaration",
        "delivery_receipt",
        "authority_reference",
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
    identity_schema = _json("schemas/student_consumption_semantic_identity_v1.json")
    manifest_schema = _json("schemas/student_consumption_manifest_v1.json")
    registry = Registry().with_resources(
        [
            (
                identity_schema["$id"],
                Resource.from_contents(identity_schema),
            )
        ]
    )
    validator = Draft202012Validator(manifest_schema, registry=registry)
    fixture = _json("fixtures/valid/native_v3_student_v1.json")
    validator.validate(fixture)

    missing_role = copy.deepcopy(fixture)
    missing_role["resources"] = [
        resource
        for resource in missing_role["resources"]
        if resource["role"] != "target_shard"
    ]
    with pytest.raises(ValidationError):
        validator.validate(missing_role)

    duplicate_resource = copy.deepcopy(fixture)
    duplicate_resource["resources"].append(duplicate_resource["resources"][0])
    with pytest.raises(ValidationError):
        validator.validate(duplicate_resource)

    missing_row_range = copy.deepcopy(fixture)
    target = next(
        resource
        for resource in missing_row_range["resources"]
        if resource["role"] == "target_shard"
    )
    del target["consumption"]["row_start"]
    with pytest.raises(ValidationError):
        validator.validate(missing_row_range)

    legacy_json_assignment = copy.deepcopy(fixture)
    assignment = next(
        resource
        for resource in legacy_json_assignment["resources"]
        if resource["role"] == "corridor_assignment"
    )
    assignment["encoding"] = "json"
    with pytest.raises(ValidationError):
        validator.validate(legacy_json_assignment)


def test_c1_fixture_declares_path_independent_role_bindings() -> None:
    fixture = _json("fixtures/valid/native_v3_student_v1.json")
    assert fixture["schema_version"] == "radjax_tome_student_consumption_manifest_v1"
    bindings = fixture["resources"]
    assert all(item["resource_id"] != item["inventory_binding"] for item in bindings)
    assignment = next(
        item for item in bindings if item["role"] == "corridor_assignment"
    )
    assert assignment["encoding"] == "npz"
    assert assignment["inventory_binding"] == "resources/03.npz"
    assert assignment["training_payload_binding"] == "resources/03.npz"
    assert fixture["semantic_identity"]["sequence"]["alignment"] == (
        "teacher_logit_position"
    )
    identity_for_digest = copy.deepcopy(fixture["semantic_identity"])
    declared_digest = identity_for_digest.pop("semantic_digest")
    assert (
        declared_digest
        == "sha256:"
        + hashlib.sha256(
            json.dumps(
                identity_for_digest, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
    )
    identity_projection = [
        (
            resource["resource_id"],
            resource["role"],
            resource["instance_id"],
            resource["semantic_digest"],
        )
        for resource in fixture["semantic_identity"]["resources"]
    ]
    manifest_projection = [
        (
            resource["resource_id"],
            resource["role"],
            resource["instance_id"],
            resource["semantic_digest"],
        )
        for resource in fixture["resources"]
    ]
    assert identity_projection == manifest_projection
    assert len({row[0] for row in manifest_projection}) == len(manifest_projection)
    assert len({row[1:3] for row in manifest_projection}) == len(manifest_projection)
    assert len({item["inventory_binding"] for item in bindings}) == len(bindings)


def test_c1_issue_registry_has_complete_named_corpus_coverage() -> None:
    registry = _json("errors/issues_v1.json")
    adversarial = _json("fixtures/adversarial/cases.json")
    assert set(registry["codes"]) == set(adversarial["coverage"])
    assert registry["ordering"] == "phase_resource_id_code"
    assert registry["dependent_failure_policy"] == (
        "suppress_dependent_checks_accumulate_independent_checks"
    )
    cases = adversarial["cases"]
    assert {case["primary_issue"] for case in cases} == set(registry["codes"])
    assert all(case["expected_issues"] == [case["primary_issue"]] for case in cases)
    assert {
        case_id for case_ids in adversarial["coverage"].values() for case_id in case_ids
    } == {case["id"] for case in cases}


def test_c1_cover_extension_is_a_closed_v3_family_extension() -> None:
    cover = _json("schemas/tome_cover_v3_student_consumption_v1.json")
    assert cover["properties"]["schema_version"] == {
        "const": "radjax_tome_cover_v3_student_consumption_v1"
    }
    assert cover["additionalProperties"] is False
    assert set(cover["required"]) >= {
        "identity",
        "training",
        "package",
        "manifests",
        "authority",
        "provenance",
        "validation",
        "student_consumption",
    }
    inventory = cover["properties"]["manifests"]["properties"]["content"]["properties"][
        "inventory"
    ]
    assert inventory["contains"]["properties"]["path"] == {
        "const": "manifests/student_consumption_v1.json"
    }


@pytest.mark.skipif(
    importlib.util.find_spec("setuptools") is None,
    reason="wheel build requires the configured setuptools backend",
)
def test_c1_assets_are_in_the_built_wheel(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(tmp_path),
            ".",
        ],
        cwd=ROOT.parents[5],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(tmp_path.glob("radjax_contract-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    asset_prefix = "radjax_contract/contracts/radjax_tome/student_consumption/v1/"
    assert asset_prefix + "contract.json" in names
    assert asset_prefix + "SHA256SUMS" in names
