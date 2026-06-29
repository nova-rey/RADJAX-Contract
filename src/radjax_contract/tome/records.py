from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from radjax_contract.provenance import stable_hash


@dataclass(frozen=True)
class TomeRecord:
    example_id: str | None = None
    text: str | None = None
    token_ids_sha256: str | None = None
    source_sha256: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def stable_identity(self) -> str | None:
        if self.example_id:
            return self.example_id
        if self.token_ids_sha256:
            return f"token_ids_sha256:{self.token_ids_sha256}"
        if self.source_sha256:
            return f"source_sha256:{self.source_sha256}"
        if self.text is not None:
            return f"text_sha256:{stable_hash(self.text)}"
        return None

    def identity_keys(self) -> dict[str, str]:
        keys: dict[str, str] = {}
        if self.example_id:
            keys["example_id"] = self.example_id
        if self.token_ids_sha256:
            keys["token_ids_sha256"] = self.token_ids_sha256
        if self.source_sha256:
            keys["source_sha256"] = self.source_sha256
        if self.text is not None:
            keys["text_sha256"] = stable_hash(self.text)
        return keys

    def to_dict(self) -> dict[str, Any]:
        return {
            "example_id": self.example_id,
            "text": self.text,
            "token_ids_sha256": self.token_ids_sha256,
            "source_sha256": self.source_sha256,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeRecord:
        return cls(
            example_id=(
                None
                if payload.get("example_id") is None
                else str(payload["example_id"])
            ),
            text=None if payload.get("text") is None else str(payload["text"]),
            token_ids_sha256=(
                None
                if payload.get("token_ids_sha256") is None
                else str(payload["token_ids_sha256"])
            ),
            source_sha256=(
                None
                if payload.get("source_sha256") is None
                else str(payload["source_sha256"])
            ),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class TomeRecordLoadResult:
    records: tuple[TomeRecord, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def load_tome_records(path: str | Path) -> TomeRecordLoadResult:
    target = Path(path)
    blockers: list[str] = []
    warnings: list[str] = []
    records: list[TomeRecord] = []
    seen_example_ids: dict[str, int] = {}
    if not target.exists():
        return TomeRecordLoadResult((), blockers=("records_missing",))
    for line_number, line in enumerate(
        target.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            blockers.append(f"records_malformed_json line={line_number}: {exc.msg}")
            continue
        if not isinstance(payload, dict):
            blockers.append(f"records_line_not_object line={line_number}")
            continue
        try:
            record = TomeRecord.from_dict(payload)
        except Exception as exc:
            blockers.append(
                f"record_invalid line={line_number}: {type(exc).__name__}: {exc}"
            )
            continue
        if record.stable_identity() is None:
            blockers.append(f"record_missing_stable_identity line={line_number}")
        if record.example_id is None:
            warnings.append(f"record_missing_example_id line={line_number}")
        elif record.example_id in seen_example_ids:
            blockers.append(f"record_duplicate_example_id {record.example_id}")
        else:
            seen_example_ids[record.example_id] = line_number
        records.append(record)
    if not records and not blockers:
        blockers.append("records_empty")
    return TomeRecordLoadResult(
        records=tuple(records),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )
