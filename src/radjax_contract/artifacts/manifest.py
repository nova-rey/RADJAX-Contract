from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CONTRACT_PACKAGE = "radjax-contract"
CONTRACT_VERSION = "0.1.0"


@dataclass(frozen=True)
class ArtifactManifest:
    producer: str
    schema_name: str
    schema_version: str = "0"
    contract_package: str = CONTRACT_PACKAGE
    contract_version: str = CONTRACT_VERSION
    artifact_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "producer": self.producer,
            "contract_package": self.contract_package,
            "contract_version": self.contract_version,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ArtifactManifest:
        return cls(
            producer=str(payload["producer"]),
            contract_package=str(payload.get("contract_package", CONTRACT_PACKAGE)),
            contract_version=str(payload.get("contract_version", CONTRACT_VERSION)),
            schema_name=str(payload["schema_name"]),
            schema_version=str(payload.get("schema_version", "0")),
            artifact_id=(
                None
                if payload.get("artifact_id") is None
                else str(payload.get("artifact_id"))
            ),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class TeacherTomeManifest(ArtifactManifest):
    producer: str = "radjax-tome"
    schema_name: str = "teacher_tome_v0"


@dataclass(frozen=True)
class TargetStoreManifest(ArtifactManifest):
    producer: str = "radjax-tome"
    schema_name: str = "target_store_v0"


@dataclass(frozen=True)
class FingerprintArtifactManifest(ArtifactManifest):
    producer: str = "radjax-tome"
    schema_name: str = "fingerprint_artifact_v0"


@dataclass(frozen=True)
class StudentArtifactManifest(ArtifactManifest):
    producer: str = "radjax-student"
    schema_name: str = "student_artifact_v0"
