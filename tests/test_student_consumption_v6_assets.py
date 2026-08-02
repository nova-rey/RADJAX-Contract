"""Static closure checks for the additive v6 candidate assets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from radjax_contract.tome import tome_student_consumption_v6_contract_asset_path

ROOT = (
    Path(__file__).parents[1]
    / "src/radjax_contract/contracts/radjax_tome/student_consumption/v6"
)


def test_v6_assets_are_closed_and_profile_is_schema_valid() -> None:
    expected = {
        path: digest
        for digest, path in (
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
    schema = json.loads(
        (ROOT / "schemas/student_consumption_profile_v6.json").read_text()
    )
    Draft202012Validator(schema).validate(
        json.loads((ROOT / "profiles/native_v3_student_v6.json").read_text())
    )
    assert (
        tome_student_consumption_v6_contract_asset_path("contract.json")
        == ROOT / "contract.json"
    )
