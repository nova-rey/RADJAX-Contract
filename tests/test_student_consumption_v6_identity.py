"""Identity-domain regressions for the additive v6 behavioral contract."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from radjax_contract.tome.student_consumption_v6 import (
    AUTHORITY_ROLES,
    ResolvedBehavioralResource,
    _parse_jsonl_bytes,
    canonical_authority_reference_identity,
    canonical_behavioral_authority_digest,
    canonical_behavioral_source_identity,
    canonical_composition_digest,
    canonical_multipart_npy_identity,
    canonical_npy_component_identity,
    canonical_selected_passport_identity,
    open_verified_student_jsonl_records_v6,
    sha256_identity,
)

V5_FIXTURE = (
    Path(__file__).parents[1]
    / "src/radjax_contract/contracts/radjax_tome/student_consumption/v5/fixtures/valid"
)


def _identity(letter: str) -> str:
    return "sha256:" + letter * 64


def _raw(path: Path) -> tuple[str, int]:
    payload = path.read_bytes()
    return sha256_identity(payload), len(payload)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _v6_package(tmp_path: Path) -> Path:
    """Build a portable whole-JSONL v6 package without claiming Tome data."""

    package = tmp_path / "package"
    shutil.copytree(V5_FIXTURE, package)
    (package / "manifests").mkdir()
    (package / "native_v3_student_v5.json").replace(
        package / "manifests/language_tokenizer_binding_v1.json"
    )
    resources = package / "resources"
    rows: list[dict[str, object]] = []

    def plain(
        role: str, value: object, *, encoding: str, schema: str = "test-v1"
    ) -> dict[str, object]:
        path = resources / f"{role}.{'jsonl' if encoding == 'jsonl' else 'json'}"
        if encoding == "jsonl":
            path.write_text(
                "".join(json.dumps(item, sort_keys=True) + "\n" for item in value),
                encoding="utf-8",
            )
        else:
            _write_json(path, value)
        digest, size = _raw(path)
        return {
            "resource_id": f"{role}/default",
            "role": role,
            "schema": schema,
            "encoding": encoding,
            "locator": path.relative_to(package).as_posix(),
            "raw_sha256": digest,
            "raw_size_bytes": size,
        }

    def multipart(
        role: str, arrays: dict[str, tuple[np.ndarray, list[str]]]
    ) -> dict[str, object]:
        binding = resources / f"{role}.json"
        _write_json(binding, {"test_only": True})
        outer_digest, outer_size = _raw(binding)
        components = []
        for name, (array, axes) in sorted(arrays.items()):
            path = resources / f"{role}.{name}.npy"
            np.save(path, array, allow_pickle=False)
            digest, size = _raw(path)
            components.append(
                {
                    "component": name,
                    "locator": path.relative_to(package).as_posix(),
                    "axes": axes,
                    "raw_sha256": digest,
                    "raw_size_bytes": size,
                }
            )
        return {
            "resource_id": f"{role}/default",
            "role": role,
            "schema": "test-v1",
            "encoding": "multipart_npy",
            "locator": binding.relative_to(package).as_posix(),
            "raw_sha256": outer_digest,
            "raw_size_bytes": outer_size,
            "components": components,
        }

    rows.extend(
        [
            multipart(
                "target_shard",
                {
                    "attention_mask": (
                        np.array([[1, 0]], dtype=np.int8),
                        ["example", "sequence_position"],
                    ),
                    "input_ids": (
                        np.array([[0, 1]], dtype=np.int32),
                        ["example", "sequence_position"],
                    ),
                },
            ),
            plain("example_registry", [{"example_id": "example-0"}], encoding="jsonl"),
            plain(
                "corridor_mode_table",
                {
                    "modes": [
                        {
                            "mode_id": 0,
                            "statistics": {
                                key: {"min": 0.0, "mean": 0.0, "max": 0.0}
                                for key in (
                                    "entropy",
                                    "top1_margin",
                                    "top8_mass",
                                    "top32_mass",
                                    "tail_mass",
                                )
                            },
                        }
                    ]
                },
                encoding="json",
            ),
            multipart(
                "corridor_assignment",
                {
                    "example_index": (np.array([0, 0], dtype=np.int32), ["coordinate"]),
                    "position": (np.array([0, 1], dtype=np.int32), ["coordinate"]),
                    "mode_id": (np.array([0, 0], dtype=np.int32), ["coordinate"]),
                    "weight": (np.array([1.0, 1.0], dtype=np.float32), ["coordinate"]),
                },
            ),
            plain(
                "selected_passport_index",
                [
                    {
                        "schema_version": "radjax_selected_passport_v6",
                        "selected_example_id": "example-0",
                        "selected_position": 0,
                        "rank": 1,
                        "selected_score": 1.0,
                        "selected_policy": "test",
                        "corridor_mode_id": 0,
                        "corridor_fingerprint_id": "fingerprint-0",
                        "corridor_assignment_status": "selected",
                        "selection_integration_config_hash": _identity("a"),
                    }
                ],
                encoding="jsonl",
            ),
            plain(
                "selected_exemplar_payload",
                [{"selected_example_id": "example-0", "selected_position": 0}],
                encoding="jsonl",
            ),
            plain(
                "authority_reference",
                {
                    "schema_version": "radjax_behavioral_authority_reference_v6",
                    "selection_integration_config_hash": _identity("a"),
                    "score_pass_authority_hash": _identity("b"),
                    "delivery_authority_hash": _identity("c"),
                },
                encoding="json",
            ),
            plain(
                "delivery_receipt",
                {"delivery_path": "two_pass_rerun_selected"},
                encoding="json",
            ),
        ]
    )
    from radjax_contract.tome import student_consumption_v6 as v6
    from radjax_contract.tome.language_tokenizer_binding_v1 import (
        validate_and_resolve_language_tokenizer_binding,
    )

    issues: list[object] = []
    for row in rows:
        identity = v6._resource_semantic_identity(package, row, issues)
        assert identity is not None, issues
        row["semantic_identity"] = identity
    language = validate_and_resolve_language_tokenizer_binding(package)
    assert language.ok and language.descriptor is not None
    resolved = [
        ResolvedBehavioralResource(
            row["resource_id"],
            row["role"],
            row["schema"],
            row["encoding"],
            row["semantic_identity"],
            row["raw_sha256"],
            row["raw_size_bytes"],
            row["locator"],
            row["role"] in AUTHORITY_ROLES,
            tuple(row.get("components", ())),
        )
        for row in rows
    ]
    authority = sorted(
        (item for item in resolved if item.authority),
        key=lambda item: (item.role, item.resource_id),
    )
    delivery = [item for item in resolved if not item.authority]
    registry = v6._registry(authority)
    target_identity = next(
        item.semantic_identity for item in resolved if item.role == "target_shard"
    )
    example_registry_identity = next(
        item.semantic_identity for item in resolved if item.role == "example_registry"
    )
    authority_reference_identity = next(
        item.semantic_identity
        for item in resolved
        if item.role == "authority_reference"
    )
    source = canonical_behavioral_source_identity(
        language_binding_digest=language.descriptor.canonical_binding_digest,
        target_semantic_identity=target_identity,
        example_registry_semantic_identity=example_registry_identity,
        target_shape=(1, 2),
        target_axes=("example", "sequence_position"),
    )
    behavioral = canonical_behavioral_authority_digest(
        language_binding_digest=language.descriptor.canonical_binding_digest,
        behavioral_source_identity=source,
        authority_registry=registry,
        required_joins=(
            "assignment_to_target_grid",
            "selected_passport_to_target",
            "selected_exemplar_to_passport",
        ),
        selection_authority_digest=authority_reference_identity,
    )
    package_identity = _identity("d")
    manifest = {
        "schema_version": "radjax_behavioral_resource_binding_v1",
        "profile_id": "native_v3_student_v6",
        "resources": rows,
        "package_semantic_identity": package_identity,
        "behavioral_authority_digest": behavioral,
        "composition_digest": canonical_composition_digest(
            behavioral_authority_digest=behavioral,
            authority_registry=registry,
            non_authority_registry=v6._registry(delivery),
            package_semantic_identity=package_identity,
        ),
    }
    _write_json(package / "manifests/behavioral_resource_binding_v1.json", manifest)
    return package


def _authority_registry() -> list[dict[str, str]]:
    return [
        {
            "resource_id": "authority_reference/default",
            "role": "authority_reference",
            "schema": "authority-v1",
            "semantic_identity": _identity("a"),
        },
        {
            "resource_id": "corridor_assignment/default",
            "role": "corridor_assignment",
            "schema": "assignment-v1",
            "semantic_identity": _identity("b"),
        },
    ]


def test_npy_component_identity_frames_semantic_metadata_and_values() -> None:
    array = np.array([[1, 2]], dtype=np.int32)
    baseline = canonical_npy_component_identity(
        role="target_shard",
        component="input_ids",
        array=array,
        axes=("example", "sequence_position"),
    )
    assert baseline != canonical_npy_component_identity(
        role="target_shard",
        component="attention_mask",
        array=array,
        axes=("example", "sequence_position"),
    )
    assert baseline != canonical_npy_component_identity(
        role="target_shard",
        component="input_ids",
        array=array.astype(np.int64),
        axes=("example", "sequence_position"),
    )
    assert baseline != canonical_npy_component_identity(
        role="target_shard",
        component="input_ids",
        array=np.array([[1, 3]], dtype=np.int32),
        axes=("example", "sequence_position"),
    )


def test_multipart_identity_is_closed_and_name_ordered() -> None:
    components = [
        {"component": "attention_mask", "semantic_identity": _identity("a")},
        {"component": "input_ids", "semantic_identity": _identity("b")},
    ]
    digest = canonical_multipart_npy_identity(
        role="target_shard", components=components
    )
    assert digest.startswith("sha256:")
    with pytest.raises(ValueError, match="name-sorted"):
        canonical_multipart_npy_identity(
            role="target_shard", components=list(reversed(components))
        )


def test_delivery_registry_changes_composition_not_behavioral_authority() -> None:
    authority = _authority_registry()
    behavioral = canonical_behavioral_authority_digest(
        language_binding_digest=_identity("c"),
        behavioral_source_identity=_identity("d"),
        authority_registry=authority,
        required_joins=("assignment_to_target",),
        selection_authority_digest=_identity("e"),
    )
    first = canonical_composition_digest(
        behavioral_authority_digest=behavioral,
        authority_registry=authority,
        non_authority_registry=[
            {
                "resource_id": "delivery_receipt/default",
                "role": "delivery_receipt",
                "schema": "receipt-v1",
                "semantic_identity": _identity("f"),
            }
        ],
        package_semantic_identity=_identity("1"),
    )
    second = canonical_composition_digest(
        behavioral_authority_digest=behavioral,
        authority_registry=authority,
        non_authority_registry=[
            {
                "resource_id": "delivery_receipt/default",
                "role": "delivery_receipt",
                "schema": "receipt-v1",
                "semantic_identity": _identity("0"),
            }
        ],
        package_semantic_identity=_identity("1"),
    )
    assert first != second


def test_closed_passport_and_authority_projections_reject_extra_fields() -> None:
    passport = {
        "schema_version": "radjax_selected_passport_v6",
        "selected_example_id": "example-0",
        "selected_position": 0,
        "rank": 1,
        "selected_score": 1.0,
        "selected_policy": "fixed",
        "corridor_mode_id": 0,
        "corridor_fingerprint_id": "fingerprint-0",
        "corridor_assignment_status": "selected",
        "selection_integration_config_hash": _identity("a"),
    }
    assert canonical_selected_passport_identity([passport]).startswith("sha256:")
    with pytest.raises(ValueError, match="closed"):
        canonical_selected_passport_identity([{**passport, "source_row": 0}])
    reference = {
        "schema_version": "radjax_behavioral_authority_reference_v6",
        "selection_integration_config_hash": _identity("a"),
        "score_pass_authority_hash": _identity("b"),
        "delivery_authority_hash": _identity("c"),
    }
    assert canonical_authority_reference_identity(reference).startswith("sha256:")


def test_ordinary_jsonl_parser_requires_complete_object_records() -> None:
    records = _parse_jsonl_bytes(b'{"example_id":"a"}\n{"example_id":"b"}\n')
    assert records == ({"example_id": "a"}, {"example_id": "b"})
    with pytest.raises(ValueError, match="JSONL"):
        _parse_jsonl_bytes(b'{"example_id":"a"}\nnot-json\n')
    with pytest.raises(ValueError, match="nonempty"):
        _parse_jsonl_bytes(b"\n")


def test_ordinary_jsonl_opening_verifies_the_complete_member_before_yield(
    tmp_path: Path,
) -> None:
    package = _v6_package(tmp_path)
    with open_verified_student_jsonl_records_v6(
        package, "example_registry/default"
    ) as records:
        assert next(records) == {"example_id": "example-0"}

    path = package / "resources/example_registry.jsonl"
    path.write_text('{"example_id":"replaced"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="BRC010_RAW_INTEGRITY_MISMATCH"):
        with open_verified_student_jsonl_records_v6(
            package, "example_registry/default"
        ):
            pass
