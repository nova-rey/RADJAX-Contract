"""Static publication checks for the closed generic v5 binding assets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = (
    Path(__file__).parents[1]
    / "src/radjax_contract/contracts/radjax_tome/student_consumption/v5"
)


def test_v5_assets_are_checksum_closed_and_schema_valid() -> None:
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
    Draft202012Validator(schemas["student_consumption_profile_v5.json"]).validate(
        json.loads((ROOT / "profiles/native_v3_student_v5.json").read_text())
    )
    Draft202012Validator(schemas["language_tokenizer_binding_v1.json"]).validate(
        json.loads((ROOT / "fixtures/valid/native_v3_student_v5.json").read_text())
    )


def test_v5_assets_state_generic_scope_and_deterministic_vector() -> None:
    contract = json.loads((ROOT / "contract.json").read_text())
    vector = json.loads(
        (ROOT / "vectors/language_tokenizer_binding_v1.json").read_text()
    )
    assert contract["profile_id"] == "native_v3_student_v5"
    assert contract["semantic_scope"] == "generic_language_tokenizer_binding_only"
    assert vector["token_domain"] == [0, vector["vocabulary_size"]]
    assert "sequence_length" in vector["nonclaims"]
