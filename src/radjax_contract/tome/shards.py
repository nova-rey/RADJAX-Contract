from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TomeShard:
    path: str
    record_count: int | None = None
    sha256: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.record_count is not None and self.record_count < 0:
            raise ValueError("TomeShard record_count must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "record_count": self.record_count,
            "sha256": self.sha256,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeShard:
        return cls(
            path=str(payload["path"]),
            record_count=(
                None
                if payload.get("record_count") is None
                else int(payload["record_count"])
            ),
            sha256=None if payload.get("sha256") is None else str(payload["sha256"]),
            metadata=dict(payload.get("metadata", {})),
        )
