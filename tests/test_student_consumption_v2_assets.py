"""Publication assets for the additive native-v3 consumption-v2 repair."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from radjax_contract.tome import (
    TOME_STUDENT_CONSUMPTION_V2_CONTRACT_PUBLICATION_VERSION,
    tome_student_consumption_v2_contract_asset_path,
    tome_student_consumption_v2_contract_root,
)


def _json(relative: str) -> object:
    root = tome_student_consumption_v2_contract_root()
    return json.loads((root / relative).read_text(encoding="utf-8"))


def test_v2_assets_are_checksum_closed_and_discoverable() -> None:
    root = tome_student_consumption_v2_contract_root()
    expected = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", maxsplit=1)
        expected[relative] = digest
    observed = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert expected == observed
    assert TOME_STUDENT_CONSUMPTION_V2_CONTRACT_PUBLICATION_VERSION == "2.0.0"
    assert tome_student_consumption_v2_contract_asset_path("contract.json").is_file()


def test_v2_schemas_and_normative_vector_are_valid() -> None:
    root = tome_student_consumption_v2_contract_root()
    schemas = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in (root / "schemas").glob("*.json")
    }
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    profile = _json("profiles/native_v3_student_v2.json")
    Draft202012Validator(schemas["student_consumption_profile_v2.json"]).validate(
        profile
    )
    registry = Registry().with_resources(
        [
            (
                schemas["student_consumption_semantic_identity_v2.json"]["$id"],
                Resource.from_contents(
                    schemas["student_consumption_semantic_identity_v2.json"]
                ),
            )
        ]
    )
    fixture = _json("fixtures/valid/native_v3_student_v2.json")
    Draft202012Validator(
        schemas["student_consumption_manifest_v2.json"], registry=registry
    ).validate(fixture)
    vector = _json("vectors/descriptor_serialization_v2.json")
    assert (
        vector["normative_material_descriptor"]["consumption_semantic_digest"]
        == (fixture["semantic_identity"]["semantic_digest"])
    )
    assignment = next(
        row for row in fixture["resources"] if row["role"] == "corridor_assignment"
    )
    assert assignment["encoding"] == "npz"
    assert assignment["consumption"]["axes"] == {
        "position_example_index": ["assignment"],
        "position": ["assignment"],
        "mode_id": ["assignment"],
        "weight": ["assignment"],
    }


def test_v2_adversarial_catalog_only_declares_reachable_contract_codes() -> None:
    codes = set(_json("errors/issues_v2.json")["codes"])
    catalog = _json("fixtures/adversarial/cases.json")
    assert catalog["completion_rule"].startswith("A public v2 resolver MUST")
    assert catalog["cases"]
    for case in catalog["cases"]:
        assert case["primary_issue"] in codes
        assert set(case["expected_issues"]) <= codes


@pytest.mark.skipif(
    importlib.util.find_spec("setuptools") is None,
    reason="wheel build requires the configured setuptools backend",
)
def test_v2_assets_are_in_the_built_wheel(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
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
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(tmp_path.glob("radjax_contract-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    prefix = "radjax_contract/contracts/radjax_tome/student_consumption/v2/"
    assert prefix + "contract.json" in names
    assert prefix + "SHA256SUMS" in names
