from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from radjax_contract.testing import production_tome_fixture_path
from radjax_contract.tome.production import (
    ArtifactLocalFingerprintId,
    ArtifactLocalModeId,
    inspect_production_tome,
    validate_production_tome,
)

ALL_CAPABILITIES = {
    "radjax.corridor.packed_assignments.v1",
    "radjax.corridor.stat_bands.v1",
    "radjax.exemplar.selected_dynamic_topk.v1",
}


def test_packaged_production_fixture_passes_full_contract() -> None:
    fixture = production_tome_fixture_path()
    result = validate_production_tome(fixture)

    assert result.status == "pass"
    assert result.blockers == ()
    assert result.artifact is not None
    assert result.artifact.cover_page.identity.cover_page_version == 2
    assert result.artifact.corridor is not None
    assert len(result.artifact.corridor.modes) >= 2
    assert result.artifact.exemplar is not None
    assert [
        payload.effective_top_k for payload in result.artifact.exemplar.payloads
    ] == [
        2,
        3,
        4,
        5,
    ]
    assert result.artifact.exemplar.delivery_paths == ("two_pass_rerun_selected",)


def test_artifact_local_identifier_types_remain_distinct() -> None:
    assert ArtifactLocalModeId.from_value(7) != ArtifactLocalFingerprintId.from_value(7)


def test_inspection_separates_validity_from_consumer_capability() -> None:
    fixture = production_tome_fixture_path()

    unsupported = inspect_production_tome(fixture)
    supported = inspect_production_tome(
        fixture,
        supported_capabilities=ALL_CAPABILITIES,
    )

    assert unsupported.structurally_valid
    assert not unsupported.consumable
    assert set(unsupported.unsupported_required_capabilities) == ALL_CAPABILITIES
    assert supported.structurally_valid
    assert supported.consumable
    assert supported.known_surfaces == ("corridor", "exemplar")
    assert supported.recommended_passes == ("corridor_pass", "exemplar_pass")


def test_unknown_optional_surface_remains_inspectable(tmp_path: Path) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    cover["behavioral_surfaces"].append(
        {
            "optional_content_roles": [],
            "prerequisites": [],
            "required_capabilities": [],
            "required_content_roles": [],
            "schema_version": "future_surface_v1",
            "semantics": {"future_field": True},
            "surface_id": "future_optional",
            "surface_kind": "future_optional_kind",
            "target_scope": {"kind": "whole_model"},
        }
    )
    _write_json(artifact / "cover_page.json", cover)

    inspection = inspect_production_tome(
        artifact,
        supported_capabilities=ALL_CAPABILITIES,
    )

    assert inspection.structurally_valid
    assert inspection.consumable
    assert inspection.unknown_surfaces == ("future_optional",)


def test_unknown_required_role_is_preserved_and_reported(tmp_path: Path) -> None:
    artifact = _copy_fixture(tmp_path)
    unknown_path = artifact / "future" / "contract.bin"
    unknown_path.parent.mkdir()
    unknown_path.write_bytes(b"future contract")
    cover = _read_json(artifact / "cover_page.json")
    cover["contents"].append(
        {
            "classification": "training_critical",
            "path": "future/contract.bin",
            "required": True,
            "role": "future_training_contract",
            "sha256": _sha256(unknown_path),
            "size_bytes": unknown_path.stat().st_size,
            "future_metadata": {"preserved": True},
        }
    )
    cover["behavioral_surfaces"][0]["required_content_roles"].append(
        "future_training_contract"
    )
    _write_json(artifact / "cover_page.json", cover)

    result = validate_production_tome(artifact)
    inspection = inspect_production_tome(
        artifact,
        supported_capabilities=ALL_CAPABILITIES,
    )

    assert result.ok
    assert result.artifact is not None
    future_ref = next(
        ref
        for ref in result.artifact.cover_page.contents
        if ref.role == "future_training_contract"
    )
    assert future_ref.metadata == {"future_metadata": {"preserved": True}}
    assert inspection.structurally_valid
    assert not inspection.consumable
    assert inspection.unknown_required_roles == ("future_training_contract",)


def test_unknown_optional_role_is_preserved_without_blocking(tmp_path: Path) -> None:
    artifact = _copy_fixture(tmp_path)
    future_path = artifact / "future-optional.json"
    _write_json(future_path, {"future": True})
    cover = _read_json(artifact / "cover_page.json")
    cover["contents"].append(
        {
            "classification": "diagnostic",
            "path": "future-optional.json",
            "required": False,
            "role": "future_optional_diagnostic",
            "sha256": _sha256(future_path),
            "size_bytes": future_path.stat().st_size,
        }
    )
    _write_json(artifact / "cover_page.json", cover)

    result = validate_production_tome(artifact)

    assert result.ok
    assert result.warnings == ("unknown_content_role: future_optional_diagnostic",)


def test_unknown_required_capability_blocks_consumption_not_parsing(
    tmp_path: Path,
) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    future_capability = "radjax.future.required.v1"
    cover["behavioral_surfaces"][0]["required_capabilities"].append(future_capability)
    cover["recommended_training_plan"]["passes"][0]["required_capabilities"].append(
        future_capability
    )
    _write_json(artifact / "cover_page.json", cover)

    inspection = inspect_production_tome(
        artifact,
        supported_capabilities=ALL_CAPABILITIES,
    )

    assert inspection.structurally_valid
    assert not inspection.consumable
    assert inspection.unsupported_required_capabilities == (future_capability,)


def test_role_index_allows_noncanonical_filename(tmp_path: Path) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    ref = _content_ref(cover, "corridor_summary")
    old_path = artifact / ref["path"]
    new_path = artifact / "renamed" / "surface-summary.data"
    new_path.parent.mkdir()
    old_path.rename(new_path)
    ref["path"] = "renamed/surface-summary.data"
    _write_json(artifact / "cover_page.json", cover)

    assert validate_production_tome(artifact).ok


@pytest.mark.parametrize(
    ("mutation", "blocker"),
    [
        ("unsupported_version", "identity_mismatch"),
        ("stale_path", "content_missing"),
        ("absolute_path", "content_path_unsafe"),
        ("stale_size", "content_size_mismatch"),
        ("hash_mismatch", "content_hash_mismatch"),
        ("duplicate_path", "content_path_duplicate"),
        ("duplicate_role", "content_role_cardinality_invalid"),
        ("omitted_required_role", "surface_required_role_missing"),
        ("unsafe_path", "content_path_unsafe"),
        ("missing_surface_role", "surface_required_role_missing"),
        ("surface_cycle", "surface_prerequisite_cycle"),
        ("bad_pass_order", "training_pass_order_invalid"),
        ("missing_pass_surface", "training_pass_surface_missing"),
    ],
)
def test_malformed_cover_pages_are_rejected(
    tmp_path: Path,
    mutation: str,
    blocker: str,
) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    if mutation == "unsupported_version":
        cover["cover_page_version"] = 999
    elif mutation == "stale_path":
        _content_ref(cover, "corridor_summary")["path"] = "missing.json"
    elif mutation == "absolute_path":
        _content_ref(cover, "corridor_summary")["path"] = "/tmp/outside.json"
    elif mutation == "stale_size":
        _content_ref(cover, "corridor_summary")["size_bytes"] += 1
    elif mutation == "hash_mismatch":
        _content_ref(cover, "corridor_summary")["sha256"] = "0" * 64
    elif mutation == "duplicate_path":
        _content_ref(cover, "corridor_summary")["path"] = _content_ref(
            cover, "corridor_mode_table"
        )["path"]
    elif mutation == "duplicate_role":
        cover["contents"].append(dict(_content_ref(cover, "corridor_summary")))
    elif mutation == "omitted_required_role":
        cover["contents"] = [
            item for item in cover["contents"] if item["role"] != "corridor_summary"
        ]
    elif mutation == "unsafe_path":
        _content_ref(cover, "corridor_summary")["path"] = "../outside.json"
    elif mutation == "missing_surface_role":
        cover["behavioral_surfaces"][0]["required_content_roles"].append(
            "future_missing_role"
        )
    elif mutation == "surface_cycle":
        cover["behavioral_surfaces"][0]["prerequisites"] = ["exemplar"]
    elif mutation == "bad_pass_order":
        cover["recommended_training_plan"]["passes"].reverse()
    elif mutation == "missing_pass_surface":
        cover["recommended_training_plan"]["passes"][0]["surface_id"] = "missing"
    _write_json(artifact / "cover_page.json", cover)

    result = validate_production_tome(artifact)

    assert not result.ok
    assert any(item.startswith(blocker) for item in result.blockers)


def test_mode_and_fingerprint_domains_cannot_be_substituted(tmp_path: Path) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    mode_ref = _content_ref(cover, "corridor_assignment_mode_id")
    fingerprint_ref = _content_ref(
        cover,
        "corridor_assignment_fingerprint_index",
    )
    mode_ref.update(
        path=fingerprint_ref["path"],
        sha256=fingerprint_ref["sha256"],
        size_bytes=fingerprint_ref["size_bytes"],
    )
    _write_json(artifact / "cover_page.json", cover)

    result = validate_production_tome(artifact)

    assert not result.ok
    assert "corridor_mode_id_domain_invalid" in "\n".join(result.blockers)


def test_packed_array_descriptor_mismatch_is_rejected(tmp_path: Path) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    manifest_ref = _content_ref(cover, "corridor_assignment_manifest")
    manifest_path = artifact / manifest_ref["path"]
    manifest = _read_json(manifest_path)
    manifest["arrays"]["weight"]["shape"] = [999]
    _write_json(manifest_path, manifest)
    _refresh_ref(manifest_ref, manifest_path)
    _write_json(artifact / "cover_page.json", cover)

    result = validate_production_tome(artifact)

    assert "corridor_assignment_descriptor_mismatch: weight" in result.blockers


def test_packed_array_length_mismatch_is_rejected(tmp_path: Path) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    weight_ref = _content_ref(cover, "corridor_assignment_weight")
    weight_path = artifact / weight_ref["path"]
    weights = np.load(weight_path, allow_pickle=False)
    np.save(weight_path, weights[:-1], allow_pickle=False)
    _refresh_ref(weight_ref, weight_path)
    manifest_ref = _content_ref(cover, "corridor_assignment_manifest")
    manifest_path = artifact / manifest_ref["path"]
    manifest = _read_json(manifest_path)
    manifest["arrays"]["weight"]["shape"] = [len(weights) - 1]
    _write_json(manifest_path, manifest)
    _refresh_ref(manifest_ref, manifest_path)
    _write_json(artifact / "cover_page.json", cover)

    result = validate_production_tome(artifact)

    assert "corridor_assignment_shape_invalid: weight" in result.blockers


def test_unknown_mode_id_is_rejected(tmp_path: Path) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    mode_ref = _content_ref(cover, "corridor_assignment_mode_id")
    mode_path = artifact / mode_ref["path"]
    modes = np.load(mode_path, allow_pickle=False)
    modes[0] = 999
    np.save(mode_path, modes, allow_pickle=False)
    _refresh_ref(mode_ref, mode_path)
    _write_json(artifact / "cover_page.json", cover)

    result = validate_production_tome(artifact)

    assert "corridor_mode_id_domain_invalid" in "\n".join(result.blockers)


def test_exemplar_index_payload_join_mismatch_is_rejected(tmp_path: Path) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    index_ref = _content_ref(cover, "selected_exemplar_index")
    index_path = artifact / index_ref["path"]
    index = _read_json(index_path)
    index["selected_exemplars"][0]["selected_position"] = 1
    _write_json(index_path, index)
    _refresh_ref(index_ref, index_path)
    _write_json(artifact / "cover_page.json", cover)

    result = validate_production_tome(artifact)

    assert "exemplar_index_payload_join_mismatch" in result.blockers


def test_exemplar_mass_mismatch_is_rejected(tmp_path: Path) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    payload_ref = _content_ref(cover, "selected_exemplar_payload_shard")
    payload_path = artifact / payload_ref["path"]
    payload = _read_json(payload_path)
    payload["selected_exemplars"][0]["top_mass"] = 0.1
    _write_json(payload_path, payload)
    _refresh_ref(payload_ref, payload_path)
    _write_json(artifact / "cover_page.json", cover)

    result = validate_production_tome(artifact)

    assert any("exemplar_top_mass_mismatch" in item for item in result.blockers)


@pytest.mark.parametrize(
    ("mutation", "blocker"),
    [
        ("dynamic_top_k", "exemplar_dynamic_top_k_mismatch"),
        ("mask", "exemplar_selection_mask_invalid"),
        ("token_id", "exemplar_token_id_out_of_range"),
        ("corridor_link", "exemplar_corridor_mode_unknown"),
    ],
)
def test_malformed_exemplar_payloads_are_rejected(
    tmp_path: Path,
    mutation: str,
    blocker: str,
) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    payload_ref = _content_ref(cover, "selected_exemplar_payload_shard")
    payload_path = artifact / payload_ref["path"]
    shard = _read_json(payload_path)
    payload = shard["selected_exemplars"][0]
    if mutation == "dynamic_top_k":
        payload["dynamic_top_k"]["effective_top_k"] = 5
    elif mutation == "mask":
        payload["top_selection_mask"][0] = False
    elif mutation == "token_id":
        payload["top_token_ids"][0] = payload["vocab_size"]
    elif mutation == "corridor_link":
        payload["corridor_mode_id"] = 999
    _write_json(payload_path, shard)
    _refresh_ref(payload_ref, payload_path)
    _write_json(artifact / "cover_page.json", cover)

    result = validate_production_tome(artifact)

    assert blocker in "\n".join(result.blockers)


def test_delivery_path_is_preserved_as_provenance_only(tmp_path: Path) -> None:
    artifact = _copy_fixture(tmp_path)
    cover = _read_json(artifact / "cover_page.json")
    for role in ("selected_exemplar_index", "selected_exemplar_payload_shard"):
        ref = _content_ref(cover, role)
        path = artifact / ref["path"]
        payload = _read_json(path)
        for item in payload["selected_exemplars"]:
            item["source_delivery_path"] = "future_delivery_route"
        _write_json(path, payload)
        _refresh_ref(ref, path)
    _write_json(artifact / "cover_page.json", cover)

    result = validate_production_tome(artifact)

    assert result.ok
    assert result.artifact is not None
    assert result.artifact.exemplar is not None
    assert result.artifact.exemplar.delivery_paths == ("future_delivery_route",)


def _copy_fixture(tmp_path: Path) -> Path:
    destination = tmp_path / "artifact"
    shutil.copytree(production_tome_fixture_path(), destination)
    return destination


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _content_ref(cover: dict, role: str) -> dict:
    return next(item for item in cover["contents"] if item["role"] == role)


def _refresh_ref(ref: dict, path: Path) -> None:
    ref["sha256"] = _sha256(path)
    ref["size_bytes"] = path.stat().st_size


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
