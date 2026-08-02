"""Identity-domain regressions for the additive v6 behavioral contract."""

from __future__ import annotations

import io
import json
import shutil
import tarfile
from gzip import GzipFile
from pathlib import Path

import numpy as np
import pytest

from radjax_contract.tome import streaming_validation as m7_validation
from radjax_contract.tome import student_consumption_v6 as v6_module
from radjax_contract.tome.streaming_validation import (
    open_streaming_tome,
    validate_streaming_tome,
)
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
    open_verified_student_m7_payload_v6,
    sha256_identity,
    validate_and_resolve_student_consumption_v6,
)

V5_FIXTURE = (
    Path(__file__).parents[1]
    / "src/radjax_contract/contracts/radjax_tome/student_consumption/v5/fixtures/valid"
)
M7_FIXTURE = Path(__file__).parent / "fixtures/v6_m7_payload.tgz"
M7_LANGUAGE_FIXTURE = Path(__file__).parent / "fixtures"


def _identity(letter: str) -> str:
    return "sha256:" + letter * 64


def _raw(path: Path) -> tuple[str, int]:
    payload = path.read_bytes()
    return sha256_identity(payload), len(payload)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _v6_package(
    tmp_path: Path,
    *,
    invalid_exemplar: bool = False,
    unknown_assignment_mode: bool = False,
    m7_archive: Path | None = None,
) -> Path:
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
                    "mode_id": (
                        np.array(
                            [1, 1] if unknown_assignment_mode else [0, 0],
                            dtype=np.int32,
                        ),
                        ["coordinate"],
                    ),
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
                [
                    {
                        "selected_example_id": "example-0",
                        "selected_position": 0,
                        "rank": 1,
                        "corridor_mode_id": 0,
                        "effective_top_k": 1,
                        "top_token_ids": [0],
                        "top_probs": [0.9 if invalid_exemplar else 1.0],
                        "top_log_probs": [0.0 if not invalid_exemplar else -0.1],
                        "top_selection_mask": [True],
                        "top_mass": 1.0,
                        "tail_mass": 0.0,
                        "bucket_masses": [],
                        "source_delivery_path": "two_pass_rerun_selected",
                    }
                ],
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
    if m7_archive is not None:
        shutil.copyfile(
            M7_LANGUAGE_FIXTURE / "v6_m7_language_tokenizer_binding_v1.json",
            package / "manifests/language_tokenizer_binding_v1.json",
        )
        shutil.copyfile(
            M7_LANGUAGE_FIXTURE / "v6_m7_tokenizer_vocabulary.jsonl",
            resources / "tokenizer_vocabulary.jsonl",
        )
        shutil.copyfile(m7_archive, resources / "selected_exemplar_payload.tgz")
        with open_streaming_tome(m7_archive) as reader:
            m7_records = list(reader)
        assert len(m7_records) == 2
        exemplar_row = next(
            row for row in rows if row["role"] == "selected_exemplar_payload"
        )
        m7_path = resources / "selected_exemplar_payload.tgz"
        m7_digest, m7_size = _raw(m7_path)
        exemplar_row.update(
            {
                "encoding": "m7_tome_archive",
                "locator": m7_path.relative_to(package).as_posix(),
                "raw_sha256": m7_digest,
                "raw_size_bytes": m7_size,
            }
        )
        target_row = next(row for row in rows if row["role"] == "target_shard")
        target_components = {
            component["component"]: component for component in target_row["components"]
        }
        np.save(
            package / target_components["input_ids"]["locator"],
            np.zeros((1, 4), dtype=np.int32),
            allow_pickle=False,
        )
        np.save(
            package / target_components["attention_mask"]["locator"],
            np.ones((1, 4), dtype=np.int8),
            allow_pickle=False,
        )
        assignment_row = next(
            row for row in rows if row["role"] == "corridor_assignment"
        )
        assignment_components = {
            component["component"]: component
            for component in assignment_row["components"]
        }
        for component, values in {
            "example_index": np.zeros(4, dtype=np.int32),
            "position": np.arange(4, dtype=np.int32),
            "mode_id": np.zeros(4, dtype=np.int32),
            "weight": np.ones(4, dtype=np.float32),
        }.items():
            np.save(
                package / assignment_components[component]["locator"],
                values,
                allow_pickle=False,
            )
        example_row = next(row for row in rows if row["role"] == "example_registry")
        passport_row = next(
            row for row in rows if row["role"] == "selected_passport_index"
        )
        example_path = package / example_row["locator"]
        passport_path = package / passport_row["locator"]
        example_path.write_text(
            json.dumps({"example_id": m7_records[0]["selected_example_id"]}) + "\n",
            encoding="utf-8",
        )
        passports = [
            {
                "schema_version": "radjax_selected_passport_v6",
                "selected_example_id": record["selected_example_id"],
                "selected_position": record["selected_position"],
                "rank": rank,
                "selected_score": record["selected_score"],
                "selected_policy": record["selected_policy"],
                "corridor_mode_id": record["corridor_mode_id"],
                "corridor_fingerprint_id": record["corridor_fingerprint_id"],
                "corridor_assignment_status": "selected",
                "selection_integration_config_hash": _identity("a"),
            }
            for rank, record in enumerate(m7_records, start=1)
        ]
        passport_path.write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in passports),
            encoding="utf-8",
        )
        for row in (target_row, assignment_row):
            for component in row["components"]:
                component_path = package / component["locator"]
                component["raw_sha256"], component["raw_size_bytes"] = _raw(
                    component_path
                )
        for row, path in ((example_row, example_path), (passport_row, passport_path)):
            row["raw_sha256"], row["raw_size_bytes"] = _raw(path)
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
        target_shape=(1, 4) if m7_archive is not None else (1, 2),
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


def _mutated_inner_exemplar_archive(tmp_path: Path) -> Path:
    """Rebuild a valid M7 archive whose payload fails only v6 semantics."""

    root = tmp_path / "m7"
    with tarfile.open(M7_FIXTURE, "r:gz") as archive:
        archive.extractall(root, filter="data")
    shard_path = root / "selected_exemplars/shards/shard-00000.jsonl"
    records = [json.loads(line) for line in shard_path.read_text().splitlines()]
    records[0]["top_probs"][0] = 0.0
    shard_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )

    def digest(path: Path) -> tuple[str, int]:
        return _raw(path)

    shard_digest, shard_size = digest(shard_path)
    sequence = m7_validation._SequenceDigest()
    index_path = root / "selected_exemplars/payload-index.jsonl"
    index_rows = [json.loads(line) for line in index_path.read_text().splitlines()]
    for row, record in zip(index_rows, records, strict=True):
        logical_id, semantic = m7_validation._semantic_record(record)
        row["logical_id"] = logical_id
        row["payload_sha256"] = m7_validation._canonical(record)
        row["payload_semantic_digest"] = semantic
        row["shard_sha256"] = shard_digest
        sequence.add({"logical_id": logical_id, "payload_semantic_digest": semantic})
    sequence_digest = sequence.finish()
    index_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in index_rows),
        encoding="utf-8",
    )
    index_digest, index_size = digest(index_path)
    shard_index_path = root / "selected_exemplars/payload-shards.jsonl"
    shard_index = json.loads(shard_index_path.read_text())
    shard_index.update(
        {
            "sha256": shard_digest,
            "size_bytes": shard_size,
            "semantic_digest": sequence_digest,
        }
    )
    shard_index_path.write_text(json.dumps(shard_index, sort_keys=True) + "\n")
    shard_index_digest, shard_index_size = digest(shard_index_path)
    layout_path = root / "selected_exemplars/payload-layout.json"
    layout = json.loads(layout_path.read_text())
    layout["sequence_digest"] = sequence_digest
    layout["payload_index"].update({"sha256": index_digest, "size_bytes": index_size})
    layout["shard_index"].update(
        {"sha256": shard_index_digest, "size_bytes": shard_index_size}
    )
    layout_path.write_text(json.dumps(layout, sort_keys=True))

    cover_path = root / "cover_page.json"
    cover = json.loads(cover_path.read_text())
    cover["identity"]["payload_sequence_digest"] = sequence_digest
    cover["identity"]["semantic_digest"] = m7_validation._canonical(
        {
            key: value
            for key, value in cover["identity"].items()
            if key != "semantic_digest"
        }
    )
    cover_path.write_text(json.dumps(cover, sort_keys=True))

    inventory_path = root / "manifests/content-manifest-inventory.jsonl"
    inventory = [json.loads(line) for line in inventory_path.read_text().splitlines()]
    for entry in inventory:
        path = root / entry["path"]
        entry["sha256"], entry["size_bytes"] = digest(path)
    inventory_path.write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in inventory),
        encoding="utf-8",
    )
    inventory_digest, inventory_size = digest(inventory_path)
    header_path = root / "manifests/content-manifest-header.json"
    header = json.loads(header_path.read_text())
    header.update(
        {
            "inventory_sha256": inventory_digest,
            "inventory_size_bytes": inventory_size,
            "semantic_identity_digest": cover["identity"]["semantic_digest"],
        }
    )
    header_path.write_text(json.dumps(header, sort_keys=True))
    header_digest, header_size = digest(header_path)
    cover["manifests"]["header"].update(
        {"sha256": header_digest, "size_bytes": header_size}
    )
    cover_path.write_text(json.dumps(cover, sort_keys=True))

    output = tmp_path / "mutated.tgz"
    with (
        output.open("wb") as raw,
        GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gzip,
    ):
        with tarfile.open(fileobj=gzip, mode="w") as archive:
            ordered = [
                root / "cover_page.json",
                root / "manifests/content-manifest-header.json",
                root / "manifests/content-manifest-inventory.jsonl",
                *(root / entry["path"] for entry in inventory),
            ]
            for path in ordered:
                payload = path.read_bytes()
                member = tarfile.TarInfo(path.relative_to(root).as_posix())
                member.size = len(payload)
                member.mtime = 0
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                member.mode = 0o644
                archive.addfile(member, io.BytesIO(payload))
    return output


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
    with pytest.raises(ValueError, match="closed"):
        canonical_selected_passport_identity(
            [{**passport, "selection_integration_config_hash": "not-a-digest"}]
        )
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


def test_v6_reuses_exemplar_semantic_validation_for_admitted_payloads(
    tmp_path: Path,
) -> None:
    result = validate_and_resolve_student_consumption_v6(
        _v6_package(tmp_path, invalid_exemplar=True)
    )
    assert [issue.code for issue in result.issues] == [
        "BRC027_EXEMPLAR_SEMANTICS_INVALID"
    ]


def test_v6_rejects_full_grid_assignments_to_undeclared_modes(tmp_path: Path) -> None:
    result = validate_and_resolve_student_consumption_v6(
        _v6_package(tmp_path, unknown_assignment_mode=True)
    )
    assert [issue.code for issue in result.issues] == ["BRC028_ASSIGNMENT_MODE_UNKNOWN"]


def test_v6_closed_manifest_schema_cannot_escape_as_validator_exception(
    tmp_path: Path,
) -> None:
    package = _v6_package(tmp_path)
    manifest_path = package / "manifests/behavioral_resource_binding_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["unexpected"] = True
    _write_json(manifest_path, manifest)
    result = validate_and_resolve_student_consumption_v6(package)
    assert [issue.code for issue in result.issues] == [
        "BRC004_RESOURCE_REGISTRY_INVALID"
    ]


def test_v6_m7_payload_admission_streaming_and_tamper_rejection(
    tmp_path: Path,
) -> None:
    package = _v6_package(tmp_path, m7_archive=M7_FIXTURE)
    result = validate_and_resolve_student_consumption_v6(package)
    assert result.ok, result.issues

    with open_verified_student_m7_payload_v6(
        package, "selected_exemplar_payload/default"
    ) as reader:
        first = next(iter(reader))
        assert first["selected_example_id"] == "corpus_000000003"
        assert reader.verification_state == "open"
    assert reader.verification_state == "closed_early"

    with open_verified_student_m7_payload_v6(
        package, "selected_exemplar_payload/default"
    ) as reader:
        assert len(list(reader)) == 2
        assert reader.verification_state == "fully_verified"

    payload = package / "resources/selected_exemplar_payload.tgz"
    payload.write_bytes(payload.read_bytes() + b"replacement")
    rejected = validate_and_resolve_student_consumption_v6(package)
    assert [issue.code for issue in rejected.issues] == [
        "BRC010_RAW_INTEGRITY_MISMATCH",
        "BRC012_REQUIRED_ROLE_MISSING",
    ]


def test_v6_m7_opener_rejects_replacement_after_resolver_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _v6_package(tmp_path, m7_archive=M7_FIXTURE)
    payload = package / "resources/selected_exemplar_payload.tgz"
    original = v6_module.validate_and_resolve_student_consumption_v6

    def replace_after_admission(*args: object, **kwargs: object) -> object:
        result = original(*args, **kwargs)
        payload.write_bytes(payload.read_bytes() + b"replacement")
        return result

    monkeypatch.setattr(
        v6_module,
        "validate_and_resolve_student_consumption_v6",
        replace_after_admission,
    )
    with pytest.raises(ValueError, match="integrity changed at open"):
        with open_verified_student_m7_payload_v6(
            package, "selected_exemplar_payload/default"
        ):
            pass


def test_v6_m7_inner_exemplar_semantic_mutation_reaches_v6_validator(
    tmp_path: Path,
) -> None:
    archive = _mutated_inner_exemplar_archive(tmp_path)
    assert validate_streaming_tome(archive).ok
    result = validate_and_resolve_student_consumption_v6(
        _v6_package(tmp_path / "package", m7_archive=archive)
    )
    assert [issue.code for issue in result.issues] == [
        "BRC027_EXEMPLAR_SEMANTICS_INVALID"
    ]
    assert result.issues[0].context["findings"] == ["TSC052_DYNAMIC_TOPK_INVALID"]
