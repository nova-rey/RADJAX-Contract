from __future__ import annotations

import hashlib
import json

import pytest

from radjax_contract.tome import (
    TOME_CONTRACT_ID,
    TOME_CONTRACT_PUBLICATION_VERSION,
    tome_contract_asset_path,
    tome_contract_root,
)


def test_v3_contract_resources_are_packaged_and_checksum_pinned() -> None:
    root = tome_contract_root()
    assert TOME_CONTRACT_ID == "radjax_tome_artifact_contract"
    assert TOME_CONTRACT_PUBLICATION_VERSION == "1.0.0"
    contract = json.loads((root / "contract.json").read_text(encoding="utf-8"))
    assert contract["publication_version"] == "1.0.0"
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


def test_v3_contract_resource_lookup_rejects_unsafe_or_unknown_paths() -> None:
    assert tome_contract_asset_path("contract.json").is_file()
    with pytest.raises(ValueError, match="normalized relative"):
        tome_contract_asset_path("../contract.json")
    with pytest.raises(ValueError, match="unknown"):
        tome_contract_asset_path("missing.json")
