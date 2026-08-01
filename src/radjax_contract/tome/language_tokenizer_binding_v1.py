"""Portable validation for the architecture-neutral v5 tokenizer binding."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

PROFILE_ID = "native_v3_student_v5"
CONTRACT_ID = "radjax_tome_student_consumption_contract"
_SCHEMA_VERSION = "radjax_language_tokenizer_binding_v1"
_MANIFEST_PATH = "manifests/language_tokenizer_binding_v1.json"
_PHASES = ("profile", "binding", "digest", "inventory", "vocabulary", "resource")


@dataclass(frozen=True)
class LanguageTokenizerBindingIssue:
    """A deterministic generic binding admission failure."""

    code: str
    phase: str
    profile_id: str
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedLanguageTokenizerResource:
    """An integrity-verified generic behavior-content resource."""

    resource_id: str
    role: str
    content_digest: str
    raw_sha256: str
    raw_size_bytes: int
    locator: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LanguageTokenizerBindingDescriptor:
    """Resolved generic tokenizer semantics, deliberately without architecture data."""

    schema_version: str
    contract_id: str
    profile_id: str
    tokenizer: dict[str, Any]
    canonical_inventory_digest: str
    canonical_binding_digest: str
    vocabulary: dict[str, Any]
    resources: tuple[ResolvedLanguageTokenizerResource, ...]
    warnings: tuple[LanguageTokenizerBindingIssue, ...]
    nonclaims: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["resources"] = [item.to_dict() for item in self.resources]
        data["warnings"] = [item.to_dict() for item in self.warnings]
        data["nonclaims"] = list(self.nonclaims)
        return data


@dataclass(frozen=True)
class LanguageTokenizerBindingValidationResult:
    ok: bool
    profile_id: str
    issues: tuple[LanguageTokenizerBindingIssue, ...]
    warnings: tuple[LanguageTokenizerBindingIssue, ...]
    descriptor: LanguageTokenizerBindingDescriptor | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "radjax_language_tokenizer_binding_validation_result_v1",
            "ok": self.ok,
            "profile_id": self.profile_id,
            "issues": [item.to_dict() for item in self.issues],
            "warnings": [item.to_dict() for item in self.warnings],
            "descriptor": None
            if self.descriptor is None
            else self.descriptor.to_dict(),
        }


def contract_root() -> Path:
    """Return the installed closed v5 contract resource directory."""

    root = files("radjax_contract").joinpath(
        "contracts", "radjax_tome", "student_consumption", "v5"
    )
    return Path(str(root))


def canonical_json_bytes(value: Any) -> bytes:
    """Encode a finite, deterministic JSON value for a normative digest."""

    _reject_negative_zero(value)
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_inventory_digest(inventory: list[dict[str, Any]]) -> str:
    """Digest the ordered semantic inventory, excluding physical delivery fields."""

    projection = [
        {
            "resource_id": row["resource_id"],
            "role": row["role"],
            "content_digest": row["content_digest"],
        }
        for row in inventory
    ]
    return _sha256(canonical_json_bytes(projection))


def canonical_language_tokenizer_binding_digest(binding: dict[str, Any]) -> str:
    """Digest exactly the v5 semantic binding projection, never transport data."""

    projection = {
        "tokenizer": binding["tokenizer"],
        "canonical_inventory_digest": binding["canonical_inventory_digest"],
        "vocabulary": binding["vocabulary"],
    }
    return _sha256(canonical_json_bytes(projection))


language_tokenizer_binding_digest = canonical_language_tokenizer_binding_digest


def validate_and_resolve_language_tokenizer_binding(
    binding_or_artifact: str | Path, *, strict: bool = False
) -> LanguageTokenizerBindingValidationResult:
    """Validate and resolve v5 generic binding resources without profile fallback.

    A direct binding JSON file is accepted for portable fixture validation. A
    package directory must contain the fixed v5 manifest path; no file name is
    guessed and no legacy profile is delegated to.
    """

    issues: list[LanguageTokenizerBindingIssue] = []
    warnings: list[LanguageTokenizerBindingIssue] = []
    source = Path(binding_or_artifact)
    located = _locate_binding(source, issues)
    if located is None:
        return _result(issues, warnings)
    root, binding_path = located
    binding = _read_binding(binding_path, issues)
    if binding is None:
        return _result(issues, warnings)
    if binding.get("profile_id") != PROFILE_ID:
        issues.append(_issue("LTB001_PROFILE_UNSUPPORTED", "profile"))
        return _result(issues, warnings)
    if binding.get("schema_version") != _SCHEMA_VERSION:
        issues.append(_issue("LTB002_BINDING_VERSION_UNSUPPORTED", "binding"))
        return _result(issues, warnings)
    if not _valid_revision(binding.get("tokenizer")):
        issues.append(_issue("LTB003_REVISION_INVALID", "binding"))
        return _result(issues, warnings)
    if not _schema_valid(binding):
        issues.append(_issue("LTB004_CANONICALIZATION_INVALID", "binding"))
        return _result(issues, warnings)
    try:
        inventory = binding["behavior_content_inventory"]
        expected_inventory = canonical_inventory_digest(inventory)
        expected_binding = canonical_language_tokenizer_binding_digest(binding)
    except (KeyError, TypeError, ValueError):
        issues.append(_issue("LTB004_CANONICALIZATION_INVALID", "digest"))
        return _result(issues, warnings)
    if binding.get("canonical_inventory_digest") != expected_inventory:
        issues.append(_issue("LTB007_INVENTORY_DIGEST_MISMATCH", "digest"))
    if binding.get("canonical_binding_digest") != expected_binding:
        issues.append(_issue("LTB005_BINDING_DIGEST_MISMATCH", "digest"))
    resources = _resolve_inventory(root, inventory, binding["vocabulary"], issues)
    vocabulary_tokens = _validate_vocabulary_resource(
        root, binding["vocabulary"], resources, issues
    )
    if vocabulary_tokens is not None:
        _validate_token_declarations(binding["vocabulary"], vocabulary_tokens, issues)
    if strict and warnings:
        issues.extend(warnings)
        warnings.clear()
    descriptor = None
    if not issues:
        descriptor = LanguageTokenizerBindingDescriptor(
            "radjax_language_tokenizer_binding_descriptor_v1",
            CONTRACT_ID,
            PROFILE_ID,
            dict(binding["tokenizer"]),
            binding["canonical_inventory_digest"],
            binding["canonical_binding_digest"],
            dict(binding["vocabulary"]),
            tuple(resources),
            tuple(warnings),
            (
                "not_an_architecture_descriptor",
                "not_a_plugin_descriptor",
                "not_a_student_loader",
                "not_a_training_policy",
                "sequence_length_outside_binding",
            ),
        )
    return _result(issues, warnings, descriptor)


@contextmanager
def open_verified_language_tokenizer_resource(
    binding_or_artifact: str | Path, resource_id: str, *, strict: bool = False
) -> Iterator[Any]:
    """Open one named v5 resource after full admission and an integrity recheck."""

    result = validate_and_resolve_language_tokenizer_binding(
        binding_or_artifact, strict=strict
    )
    if not result.ok or result.descriptor is None:
        raise ValueError(
            "language/tokenizer binding validation failed: "
            + ",".join(item.code for item in result.issues)
        )
    resource = next(
        (
            item
            for item in result.descriptor.resources
            if item.resource_id == resource_id
        ),
        None,
    )
    if resource is None:
        raise ValueError(f"unknown language/tokenizer resource: {resource_id}")
    located = _locate_binding(Path(binding_or_artifact), [])
    if located is None:
        raise ValueError("language/tokenizer binding is unavailable at open")
    root, _ = located
    path = root / resource.locator
    if (
        not path.is_file()
        or path.stat().st_size != resource.raw_size_bytes
        or _file_digest(path) != resource.raw_sha256
    ):
        raise ValueError("language/tokenizer resource integrity changed at open")
    with path.open("rb") as handle:
        yield handle


open_verified_language_tokenizer_binding_resource = (
    open_verified_language_tokenizer_resource
)


def _locate_binding(
    source: Path, issues: list[LanguageTokenizerBindingIssue]
) -> tuple[Path, Path] | None:
    if source.is_file() and source.suffix == ".json":
        return source.parent, source
    if source.is_dir():
        manifest = source / _MANIFEST_PATH
        if manifest.is_file():
            return source, manifest
    issues.append(
        _issue("LTB011_RESOURCE_UNAVAILABLE", "resource", locator=str(source))
    )
    return None


def _read_binding(
    path: Path, issues: list[LanguageTokenizerBindingIssue]
) -> dict[str, Any] | None:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        issues.append(_issue("LTB004_CANONICALIZATION_INVALID", "binding"))
        return None
    if not isinstance(value, dict):
        issues.append(_issue("LTB004_CANONICALIZATION_INVALID", "binding"))
        return None
    return value


def _schema_valid(binding: dict[str, Any]) -> bool:
    try:
        schema = json.loads(
            (contract_root() / "schemas/language_tokenizer_binding_v1.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema).validate(binding)
        canonical_json_bytes(binding)
    except (OSError, TypeError, ValueError, json.JSONDecodeError, ValidationError):
        return False
    return True


def _valid_revision(tokenizer: Any) -> bool:
    if not isinstance(tokenizer, dict):
        return False
    revision = tokenizer.get("revision")
    return (
        isinstance(revision, dict)
        and set(revision) == {"kind", "value"}
        and revision.get("kind")
        in {"git_commit", "immutable_release", "content_digest"}
        and isinstance(revision.get("value"), str)
        and bool(revision["value"])
    )


def _resolve_inventory(
    root: Path,
    inventory: list[dict[str, Any]],
    vocabulary: dict[str, Any],
    issues: list[LanguageTokenizerBindingIssue],
) -> list[ResolvedLanguageTokenizerResource]:
    if (
        not inventory
        or [row["resource_id"] for row in inventory]
        != sorted(row["resource_id"] for row in inventory)
        or len({row["resource_id"] for row in inventory}) != len(inventory)
    ):
        issues.append(_issue("LTB006_INVENTORY_INVALID", "inventory"))
        return []
    vocabulary_rows = [row for row in inventory if row["role"] == "vocabulary"]
    if (
        len(vocabulary_rows) != 1
        or vocabulary_rows[0]["resource_id"] != vocabulary["resource_id"]
    ):
        issues.append(_issue("LTB006_INVENTORY_INVALID", "inventory"))
        return []
    resolved: list[ResolvedLanguageTokenizerResource] = []
    for row in inventory:
        locator = row["inventory_binding"]
        if not _safe(locator):
            issues.append(
                _issue(
                    "LTB006_INVENTORY_INVALID",
                    "inventory",
                    resource_id=row["resource_id"],
                )
            )
            continue
        path = root / locator
        if not path.is_file():
            issues.append(
                _issue(
                    "LTB011_RESOURCE_UNAVAILABLE",
                    "resource",
                    resource_id=row["resource_id"],
                )
            )
            continue
        observed = _file_digest(path)
        if (
            path.stat().st_size != row["raw_size_bytes"]
            or observed != row["raw_sha256"]
            or observed != row["content_digest"]
        ):
            issues.append(
                _issue(
                    "LTB012_RESOURCE_INTEGRITY_MISMATCH",
                    "resource",
                    resource_id=row["resource_id"],
                )
            )
            continue
        resolved.append(
            ResolvedLanguageTokenizerResource(
                row["resource_id"],
                row["role"],
                row["content_digest"],
                row["raw_sha256"],
                row["raw_size_bytes"],
                locator,
            )
        )
    return resolved


def _validate_vocabulary_resource(
    root: Path,
    vocabulary: dict[str, Any],
    resources: list[ResolvedLanguageTokenizerResource],
    issues: list[LanguageTokenizerBindingIssue],
) -> dict[int, bytes] | None:
    resource = next(
        (item for item in resources if item.resource_id == vocabulary["resource_id"]),
        None,
    )
    if resource is None:
        return None
    path = root / resource.locator
    data = path.read_bytes()
    if (
        resource.content_digest != vocabulary["vocabulary_map_digest"]
        or vocabulary["vocabulary_map_digest"] != vocabulary["vocabulary_identity"]
    ):
        issues.append(_issue("LTB009_VOCABULARY_DIGEST_MISMATCH", "vocabulary"))
        return None
    if b"\r" in data or not data.endswith(b"\n"):
        issues.append(_issue("LTB008_VOCABULARY_INVALID", "vocabulary"))
        return None
    tokens: dict[int, bytes] = {}
    for index, line in enumerate(data.splitlines()):
        try:
            row = json.loads(line, object_pairs_hook=_unique_object)
            if (
                not isinstance(row, dict)
                or set(row) != {"token_id", "token_utf8_b64"}
                or isinstance(row.get("token_id"), bool)
                or not isinstance(row.get("token_id"), int)
                or row["token_id"] != index
                or canonical_json_bytes(row) != line
            ):
                raise ValueError
            token = base64.b64decode(row["token_utf8_b64"], validate=True)
            token.decode("utf-8")
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            issues.append(_issue("LTB013_TOKEN_DOMAIN_INVALID", "vocabulary"))
            return None
        tokens[index] = token
    size = vocabulary["vocabulary_size"]
    domain = vocabulary["token_domain"]
    if domain != {"start": 0, "end_exclusive": size} or list(tokens) != list(
        range(size)
    ):
        issues.append(_issue("LTB013_TOKEN_DOMAIN_INVALID", "vocabulary"))
        return None
    return tokens


def _validate_token_declarations(
    vocabulary: dict[str, Any],
    tokens: dict[int, bytes],
    issues: list[LanguageTokenizerBindingIssue],
) -> None:
    size = vocabulary["vocabulary_size"]
    added = vocabulary["added_tokens"]
    reserved = vocabulary["reserved_token_ids"]
    special = vocabulary["special_tokens"]

    def valid_ids(values: list[Any]) -> bool:
        return all(
            isinstance(value, int) and not isinstance(value, bool) and 0 <= value < size
            for value in values
        )

    try:
        added_ids = [row["token_id"] for row in added]
        added_bytes = [
            base64.b64decode(row["token_utf8_b64"], validate=True) for row in added
        ]
    except (KeyError, TypeError, ValueError):
        issues.append(_issue("LTB010_SPECIAL_TOKEN_INVALID", "vocabulary"))
        return
    if (
        added_ids != sorted(added_ids)
        or len(set(added_ids)) != len(added_ids)
        or not valid_ids(added_ids)
        or any(
            tokens[token_id] != token
            for token_id, token in zip(added_ids, added_bytes, strict=True)
        )
        or reserved != sorted(reserved)
        or not valid_ids(reserved)
        or len(set(reserved)) != len(reserved)
        or [row["name"] for row in special] != sorted(row["name"] for row in special)
        or len({row["name"] for row in special}) != len(special)
        or not valid_ids([row["token_id"] for row in special])
    ):
        issues.append(_issue("LTB010_SPECIAL_TOKEN_INVALID", "vocabulary"))


def _safe(value: str) -> bool:
    pure = PurePosixPath(value)
    return (
        bool(value)
        and not pure.is_absolute()
        and ".." not in pure.parts
        and pure.as_posix() == value
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_negative_zero(value: Any) -> None:
    if isinstance(value, float):
        if value == 0 and str(value).startswith("-"):
            raise ValueError("negative zero is not canonical")
    elif isinstance(value, dict):
        for item in value.values():
            _reject_negative_zero(item)
    elif isinstance(value, list):
        for item in value:
            _reject_negative_zero(item)


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _issue(code: str, phase: str, **context: Any) -> LanguageTokenizerBindingIssue:
    return LanguageTokenizerBindingIssue(code, phase, PROFILE_ID, context)


def _result(
    issues: list[LanguageTokenizerBindingIssue],
    warnings: list[LanguageTokenizerBindingIssue],
    descriptor: LanguageTokenizerBindingDescriptor | None = None,
) -> LanguageTokenizerBindingValidationResult:
    phase_order = {phase: index for index, phase in enumerate(_PHASES)}
    ordered = tuple(
        sorted(
            issues,
            key=lambda item: (
                phase_order[item.phase],
                item.context.get("resource_id", ""),
                item.code,
            ),
        )
    )
    ordered_warnings = tuple(
        sorted(
            warnings,
            key=lambda item: (
                phase_order[item.phase],
                item.context.get("resource_id", ""),
                item.code,
            ),
        )
    )
    return LanguageTokenizerBindingValidationResult(
        not ordered,
        PROFILE_ID,
        ordered,
        ordered_warnings,
        None if ordered else descriptor,
    )


__all__ = [
    "CONTRACT_ID",
    "PROFILE_ID",
    "LanguageTokenizerBindingDescriptor",
    "LanguageTokenizerBindingIssue",
    "LanguageTokenizerBindingValidationResult",
    "ResolvedLanguageTokenizerResource",
    "canonical_inventory_digest",
    "canonical_json_bytes",
    "canonical_language_tokenizer_binding_digest",
    "contract_root",
    "language_tokenizer_binding_digest",
    "open_verified_language_tokenizer_binding_resource",
    "open_verified_language_tokenizer_resource",
    "validate_and_resolve_language_tokenizer_binding",
]
