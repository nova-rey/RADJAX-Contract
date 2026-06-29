from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from radjax_contract.tome.compression import TomeCompression
from radjax_contract.tome.manifest import TomeRole
from radjax_contract.tome.payloads import TomePayloadFormat

COVER_PAGE_KIND = "radjax_tome_cover_page"
COVER_PAGE_VERSION = "0"


@dataclass(frozen=True)
class TomeTeacherSummary:
    teacher_id: str
    teacher_family: str
    backend: str
    teacher_dtype: str | None = None
    teacher_vocab_size: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "teacher_id": self.teacher_id,
            "teacher_family": self.teacher_family,
            "backend": self.backend,
            "teacher_dtype": self.teacher_dtype,
            "teacher_vocab_size": self.teacher_vocab_size,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeTeacherSummary:
        return cls(
            teacher_id=str(payload.get("teacher_id", "")),
            teacher_family=str(payload.get("teacher_family", "")),
            backend=str(payload.get("backend", "")),
            teacher_dtype=(
                None
                if payload.get("teacher_dtype") is None
                else str(payload.get("teacher_dtype"))
            ),
            teacher_vocab_size=(
                None
                if payload.get("teacher_vocab_size") is None
                else int(payload.get("teacher_vocab_size"))
            ),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class TomeCorpusSource:
    source_id: str
    source_type: str
    description: str | None = None
    record_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "description": self.description,
            "record_count": self.record_count,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeCorpusSource:
        return cls(
            source_id=str(payload.get("source_id", "")),
            source_type=str(payload.get("source_type", "")),
            description=(
                None
                if payload.get("description") is None
                else str(payload["description"])
            ),
            record_count=(
                None
                if payload.get("record_count") is None
                else int(payload.get("record_count"))
            ),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class TomeCorpusSummary:
    summary: str
    sources: tuple[TomeCorpusSource, ...] = ()
    contains_synthetic_examples: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "sources": [source.to_dict() for source in self.sources],
            "contains_synthetic_examples": self.contains_synthetic_examples,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeCorpusSummary:
        return cls(
            summary=str(payload.get("summary", "")),
            sources=tuple(
                TomeCorpusSource.from_dict(dict(source))
                for source in payload.get("sources", ())
            ),
            contains_synthetic_examples=bool(
                payload.get("contains_synthetic_examples", False)
            ),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class TomeContentsSummary:
    role: TomeRole
    record_count: int
    sequence_length: int
    payload_format: TomePayloadFormat
    compression: TomeCompression = field(default_factory=TomeCompression)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "record_count": self.record_count,
            "sequence_length": self.sequence_length,
            "payload_format": self.payload_format.value,
            "compression": self.compression.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeContentsSummary:
        return cls(
            role=TomeRole(str(payload.get("role", ""))),
            record_count=int(payload.get("record_count", -1)),
            sequence_length=int(payload.get("sequence_length", -1)),
            payload_format=TomePayloadFormat(str(payload.get("payload_format", ""))),
            compression=TomeCompression.from_dict(dict(payload.get("compression", {}))),
        )


@dataclass(frozen=True)
class TomeExemplarSummary:
    exemplar_count: int = 0
    exemplar_kinds: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "exemplar_count": self.exemplar_count,
            "exemplar_kinds": list(self.exemplar_kinds),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeExemplarSummary:
        return cls(
            exemplar_count=int(payload.get("exemplar_count", 0)),
            exemplar_kinds=tuple(
                str(item) for item in payload.get("exemplar_kinds", ())
            ),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class TomeBehavioralSummary:
    included: bool = False
    mode_count: int = 0
    mode_ids: tuple[str, ...] = ()
    exemplar_count: int = 0
    exemplar_summary: TomeExemplarSummary | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "included": self.included,
            "mode_count": self.mode_count,
            "mode_ids": list(self.mode_ids),
            "exemplar_count": self.exemplar_count,
            "exemplar_summary": (
                None
                if self.exemplar_summary is None
                else self.exemplar_summary.to_dict()
            ),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeBehavioralSummary:
        exemplar_payload = payload.get("exemplar_summary")
        return cls(
            included=bool(payload.get("included", False)),
            mode_count=int(payload.get("mode_count", 0)),
            mode_ids=tuple(str(item) for item in payload.get("mode_ids", ())),
            exemplar_count=int(payload.get("exemplar_count", 0)),
            exemplar_summary=(
                None
                if exemplar_payload is None
                else TomeExemplarSummary.from_dict(dict(exemplar_payload))
            ),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class TomeSplitSummary:
    split_role: TomeRole
    known_sibling_splits: tuple[str, ...] = ()
    disjointness_checked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "split_role": self.split_role.value,
            "known_sibling_splits": list(self.known_sibling_splits),
            "disjointness_checked": self.disjointness_checked,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeSplitSummary:
        return cls(
            split_role=TomeRole(str(payload.get("split_role", ""))),
            known_sibling_splits=tuple(
                str(item) for item in payload.get("known_sibling_splits", ())
            ),
            disjointness_checked=bool(payload.get("disjointness_checked", False)),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class TomeStudentConsumptionSummary:
    expected_adapter: str
    implemented_by_contract: bool
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_adapter": self.expected_adapter,
            "implemented_by_contract": self.implemented_by_contract,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeStudentConsumptionSummary:
        return cls(
            expected_adapter=str(payload.get("expected_adapter", "")),
            implemented_by_contract=bool(payload.get("implemented_by_contract", False)),
            notes=None if payload.get("notes") is None else str(payload.get("notes")),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class TomeCoverPage:
    title: str
    description: str
    teacher: TomeTeacherSummary
    corpus: TomeCorpusSummary
    contents: TomeContentsSummary
    behavioral_fingerprint: TomeBehavioralSummary
    splits: TomeSplitSummary
    student_consumption: TomeStudentConsumptionSummary
    cover_page_kind: str = COVER_PAGE_KIND
    cover_page_version: str = COVER_PAGE_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cover_page_kind": self.cover_page_kind,
            "cover_page_version": self.cover_page_version,
            "title": self.title,
            "description": self.description,
            "teacher": self.teacher.to_dict(),
            "corpus": self.corpus.to_dict(),
            "contents": self.contents.to_dict(),
            "behavioral_fingerprint": self.behavioral_fingerprint.to_dict(),
            "splits": self.splits.to_dict(),
            "student_consumption": self.student_consumption.to_dict(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeCoverPage:
        missing = [
            key
            for key in REQUIRED_COVER_PAGE_SECTIONS
            if key not in payload or not isinstance(payload[key], dict)
        ]
        if missing:
            raise ValueError(f"missing_required_sections: {','.join(missing)}")
        return cls(
            cover_page_kind=str(payload.get("cover_page_kind", "")),
            cover_page_version=str(payload.get("cover_page_version", "")),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            teacher=TomeTeacherSummary.from_dict(dict(payload["teacher"])),
            corpus=TomeCorpusSummary.from_dict(dict(payload["corpus"])),
            contents=TomeContentsSummary.from_dict(dict(payload["contents"])),
            behavioral_fingerprint=TomeBehavioralSummary.from_dict(
                dict(payload["behavioral_fingerprint"])
            ),
            splits=TomeSplitSummary.from_dict(dict(payload["splits"])),
            student_consumption=TomeStudentConsumptionSummary.from_dict(
                dict(payload["student_consumption"])
            ),
            metadata=dict(payload.get("metadata", {})),
        )


REQUIRED_COVER_PAGE_SECTIONS = (
    "teacher",
    "corpus",
    "contents",
    "behavioral_fingerprint",
    "splits",
    "student_consumption",
)


@dataclass(frozen=True)
class TomeCoverPageLoadResult:
    cover_page: TomeCoverPage | None = None
    raw_payload: dict[str, Any] | None = None
    blockers: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.blockers and self.cover_page is not None


def load_tome_cover_page(path: str | Path) -> TomeCoverPageLoadResult:
    cover_path = Path(path)
    if cover_path.is_dir():
        cover_path = cover_path / "cover_page.json"
    if not cover_path.exists():
        return TomeCoverPageLoadResult(blockers=("cover_page_missing",))
    try:
        payload = json.loads(cover_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return TomeCoverPageLoadResult(
            blockers=(f"cover_page_malformed_json: {exc.msg}",)
        )
    if not isinstance(payload, dict):
        return TomeCoverPageLoadResult(blockers=("cover_page_not_object",))
    try:
        cover_page = TomeCoverPage.from_dict(payload)
    except Exception as exc:
        return TomeCoverPageLoadResult(
            raw_payload=payload,
            blockers=(f"cover_page_invalid: {type(exc).__name__}: {exc}",),
        )
    blockers = _cover_page_header_blockers(cover_page)
    return TomeCoverPageLoadResult(
        cover_page=cover_page,
        raw_payload=payload,
        blockers=tuple(blockers),
    )


def _cover_page_header_blockers(cover_page: TomeCoverPage) -> list[str]:
    blockers: list[str] = []
    if cover_page.cover_page_kind != COVER_PAGE_KIND:
        blockers.append(f"cover_page_kind_invalid: {cover_page.cover_page_kind}")
    if cover_page.cover_page_version != COVER_PAGE_VERSION:
        blockers.append(f"cover_page_version_invalid: {cover_page.cover_page_version}")
    return blockers
