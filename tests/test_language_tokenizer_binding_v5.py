"""Public v5 language/tokenizer binding resolver regressions."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from radjax_contract.tome import (
    canonical_inventory_digest,
    canonical_language_tokenizer_binding_digest,
    open_verified_language_tokenizer_resource,
    tome_student_consumption_v5_contract_asset_path,
    tome_student_consumption_v5_contract_root,
    validate_and_resolve_language_tokenizer_binding,
    validate_and_resolve_student_consumption,
)

ROOT = (
    Path(__file__).parents[1]
    / "src/radjax_contract/contracts/radjax_tome/student_consumption/v5"
)


def _binding_copy(tmp_path: Path) -> Path:
    fixture = ROOT / "fixtures/valid"
    target = tmp_path / "package"
    shutil.copytree(fixture, target)
    return target / "native_v3_student_v5.json"


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_binding(path: Path, binding: dict[str, object]) -> None:
    path.write_text(json.dumps(binding, sort_keys=True), encoding="utf-8")


def _refresh_semantic_digests(binding: dict[str, object]) -> None:
    inventory = binding["behavior_content_inventory"]
    assert isinstance(inventory, list)
    binding["canonical_inventory_digest"] = canonical_inventory_digest(inventory)
    binding["canonical_binding_digest"] = canonical_language_tokenizer_binding_digest(
        binding
    )


def test_v5_valid_binding_resolves_generic_resources_and_vector() -> None:
    binding_path = ROOT / "fixtures/valid/native_v3_student_v5.json"
    result = validate_and_resolve_language_tokenizer_binding(binding_path)
    assert result.ok, result.issues
    assert result.descriptor is not None
    assert result.descriptor.vocabulary["vocabulary_size"] == 4
    assert result.descriptor.nonclaims == (
        "not_an_architecture_descriptor",
        "not_a_plugin_descriptor",
        "not_a_student_loader",
        "not_a_training_policy",
        "sequence_length_outside_binding",
    )
    vector = json.loads(
        (ROOT / "vectors/language_tokenizer_binding_v1.json").read_text()
    )
    assert (
        result.descriptor.canonical_inventory_digest
        == vector["canonical_inventory_digest"]
    )
    assert (
        result.descriptor.canonical_binding_digest == vector["canonical_binding_digest"]
    )
    with open_verified_language_tokenizer_resource(
        binding_path, "tokenizer_vocabulary"
    ) as handle:
        assert handle.read().startswith(b'{"token_id":0')


def test_v5_router_requires_explicit_v5_directory_manifest(tmp_path: Path) -> None:
    binding_path = _binding_copy(tmp_path)
    package = binding_path.parent
    manifest = package / "manifests/language_tokenizer_binding_v1.json"
    manifest.parent.mkdir()
    binding_path.replace(manifest)
    result = validate_and_resolve_student_consumption(
        package, profile_id="native_v3_student_v5"
    )
    assert result.ok, result.issues
    with pytest.raises(ValueError, match="unknown language/tokenizer resource"):
        with open_verified_language_tokenizer_resource(package, "not-present"):
            pass


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda path, binding: binding.update(
                {"schema_version": "radjax_language_tokenizer_binding_v0"}
            ),
            "LTB002_BINDING_VERSION_UNSUPPORTED",
        ),
        (
            lambda path, binding: binding["tokenizer"].update(
                {"revision": {"kind": "branch", "value": "main"}}
            ),
            "LTB003_REVISION_INVALID",
        ),
        (
            lambda path, binding: binding["vocabulary"]["special_tokens"][0].update(
                {"token_id": 4}
            ),
            "LTB010_SPECIAL_TOKEN_INVALID",
        ),
    ],
)
def test_v5_binding_adversarial_semantics_are_fail_closed(
    tmp_path: Path, mutate: object, expected: str
) -> None:
    binding_path = _binding_copy(tmp_path)
    binding = json.loads(binding_path.read_text())
    mutate(binding_path, binding)
    if expected == "LTB010_SPECIAL_TOKEN_INVALID":
        _refresh_semantic_digests(binding)
    _write_binding(binding_path, binding)
    result = validate_and_resolve_language_tokenizer_binding(binding_path)
    assert [issue.code for issue in result.issues] == [expected]


def test_v5_domain_and_resource_integrity_fail_closed(tmp_path: Path) -> None:
    binding_path = _binding_copy(tmp_path)
    binding = json.loads(binding_path.read_text())
    vocab_path = binding_path.parent / "resources/vocabulary.jsonl"
    rows = vocab_path.read_text().splitlines()
    rows[1] = rows[1].replace('"token_id":1', '"token_id":5')
    vocab_path.write_text("\n".join(rows) + "\n")
    observed = _digest(vocab_path)
    resource = binding["behavior_content_inventory"][0]
    resource.update(
        {
            "content_digest": observed,
            "raw_sha256": observed,
            "raw_size_bytes": vocab_path.stat().st_size,
        }
    )
    binding["vocabulary"].update(
        {"vocabulary_map_digest": observed, "vocabulary_identity": observed}
    )
    _refresh_semantic_digests(binding)
    _write_binding(binding_path, binding)
    result = validate_and_resolve_language_tokenizer_binding(binding_path)
    assert [issue.code for issue in result.issues] == ["LTB013_TOKEN_DOMAIN_INVALID"]

    binding_path = _binding_copy(tmp_path / "tamper")
    vocab_path = binding_path.parent / "resources/vocabulary.jsonl"
    vocab_path.write_bytes(vocab_path.read_bytes() + b"x")
    result = validate_and_resolve_language_tokenizer_binding(binding_path)
    assert [issue.code for issue in result.issues] == [
        "LTB012_RESOURCE_INTEGRITY_MISMATCH"
    ]


def test_v5_digest_excludes_physical_resource_locator(tmp_path: Path) -> None:
    binding_path = _binding_copy(tmp_path)
    binding = json.loads(binding_path.read_text())
    original = binding["canonical_binding_digest"]
    old = binding_path.parent / "resources/vocabulary.jsonl"
    new = binding_path.parent / "moved/vocabulary.jsonl"
    new.parent.mkdir()
    old.replace(new)
    binding["behavior_content_inventory"][0]["inventory_binding"] = (
        "moved/vocabulary.jsonl"
    )
    _write_binding(binding_path, binding)
    result = validate_and_resolve_language_tokenizer_binding(binding_path)
    assert result.ok, result.issues
    assert result.descriptor is not None
    assert result.descriptor.canonical_binding_digest == original


def test_v5_publication_discovery_is_safe_and_assets_ship_in_wheel(
    tmp_path: Path,
) -> None:
    assert tome_student_consumption_v5_contract_root() == ROOT
    assert tome_student_consumption_v5_contract_asset_path("contract.json").is_file()
    with pytest.raises(ValueError):
        tome_student_consumption_v5_contract_asset_path("../v4/contract.json")
    if importlib.util.find_spec("setuptools") is None:
        pytest.skip("wheel build requires the configured setuptools backend")
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
    prefix = "radjax_contract/contracts/radjax_tome/student_consumption/v5/"
    assert prefix + "contract.json" in names
    assert prefix + "SHA256SUMS" in names
    installed = tmp_path / "installed"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(installed),
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(installed)
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from radjax_contract.tome import "
            "tome_student_consumption_v5_contract_asset_path; "
            "assert tome_student_consumption_v5_contract_asset_path("
            "'contract.json').is_file()",
        ],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
