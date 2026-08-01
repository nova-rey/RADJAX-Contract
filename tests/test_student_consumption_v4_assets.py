"""Static publication checks for the explicit native-v4 consumption profile."""

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

from radjax_contract.tome.contract_publication import (
    tome_student_consumption_v4_contract_asset_path,
    tome_student_consumption_v4_contract_root,
)

ROOT = (
    Path(__file__).parents[1]
    / "src/radjax_contract/contracts/radjax_tome/student_consumption/v4"
)


def _json(relative: str) -> object:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_v4_assets_are_checksum_closed_and_schema_valid() -> None:
    assert tome_student_consumption_v4_contract_root() == ROOT
    assert tome_student_consumption_v4_contract_asset_path("contract.json").is_file()
    expected = {
        relative: digest
        for digest, relative in (
            line.split("  ", maxsplit=1)
            for line in (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        )
    }
    observed = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in ROOT.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert expected == observed

    schemas = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in (ROOT / "schemas").glob("*.json")
    }
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    Draft202012Validator(schemas["student_consumption_profile_v4.json"]).validate(
        _json("profiles/native_v3_student_v4.json")
    )
    identity = schemas["student_consumption_semantic_identity_v4.json"]
    registry = Registry().with_resources(
        [(identity["$id"], Resource.from_contents(identity))]
    )
    Draft202012Validator(
        schemas["student_consumption_manifest_v4.json"], registry=registry
    ).validate(_json("fixtures/valid/native_v3_student_v4.json"))


def test_v4_vectors_require_explicit_declarations_and_no_v2_fallback() -> None:
    contract = _json("contract.json")
    vector = _json("vectors/descriptor_serialization_v4.json")
    catalog = _json("fixtures/catalog.json")
    assert contract["profile_id"] == "native_v3_student_v4"
    assert contract["profile_negotiation"] == (
        "explicit_exact_profile_id_no_v3_to_v2_fallback"
    )
    assert contract["supersedes_for_new_production"] == "native_v3_student_v2"
    declarations = vector["normative_material_descriptor"][
        "required_consumption_declarations"
    ]
    assert declarations == {
        "row_range": {"kind": "row_range_declaration"},
        "delivery_receipt": {"kind": "delivery_receipt"},
        "authority_reference": {"kind": "authority_reference"},
    }
    assert "MUST NOT fall back to v2" in catalog["regeneration"]


@pytest.mark.skipif(
    importlib.util.find_spec("setuptools") is None,
    reason="wheel build requires the configured setuptools backend",
)
def test_v4_assets_are_in_the_built_wheel(tmp_path: Path) -> None:
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
    prefix = "radjax_contract/contracts/radjax_tome/student_consumption/v4/"
    assert prefix + "contract.json" in names
    assert prefix + "SHA256SUMS" in names
