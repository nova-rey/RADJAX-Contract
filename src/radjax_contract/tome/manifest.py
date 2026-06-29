from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from radjax_contract.artifacts.manifest import CONTRACT_PACKAGE, CONTRACT_VERSION
from radjax_contract.tome.payloads import TomePayloadFormat
from radjax_contract.tome.shards import TomeShard
from radjax_contract.vocab import VocabContract


class TomeRole(StrEnum):
    TRAINING = "training"
    CALIBRATION = "calibration"
    FINAL_TEST = "final_test"
    VALIDATION = "validation"
    SMOKE = "smoke"


@dataclass(frozen=True)
class TomeManifest:
    artifact_kind: str = "radjax_tome"
    schema_version: str = "0"
    contract_package: str = CONTRACT_PACKAGE
    contract_version: str = CONTRACT_VERSION
    producer: str = "radjax-tome"
    artifact_id: str | None = None
    role: TomeRole = TomeRole.TRAINING
    payload_format: TomePayloadFormat = TomePayloadFormat.DENSE_LOGITS_V0
    vocab_contract: VocabContract | None = None
    record_count: int | None = None
    sequence_length: int | None = None
    shard_count: int = 1
    shards: tuple[TomeShard, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.record_count is not None and self.record_count < 0:
            raise ValueError("record_count must be >= 0")
        if self.sequence_length is not None and self.sequence_length <= 0:
            raise ValueError("sequence_length must be > 0")
        if self.shard_count <= 0:
            raise ValueError("shard_count must be > 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_kind": self.artifact_kind,
            "schema_version": self.schema_version,
            "contract_package": self.contract_package,
            "contract_version": self.contract_version,
            "producer": self.producer,
            "artifact_id": self.artifact_id,
            "role": self.role.value,
            "payload_format": self.payload_format.value,
            "vocab_contract": (
                None if self.vocab_contract is None else self.vocab_contract.to_dict()
            ),
            "record_count": self.record_count,
            "sequence_length": self.sequence_length,
            "shard_count": self.shard_count,
            "shards": [shard.to_dict() for shard in self.shards],
            "metadata": dict(self.metadata),
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeManifest:
        artifact_kind = str(payload.get("artifact_kind", ""))
        if not artifact_kind and payload.get("schema_name") == "teacher_tome_v0":
            artifact_kind = "radjax_tome"
        metadata = dict(payload.get("metadata", {}))
        payload_format = _payload_format_from_payload(payload, metadata)
        role = _role_from_payload(payload, metadata)
        vocab_payload = payload.get("vocab_contract") or metadata.get("vocab_contract")
        record_count = payload.get("record_count", metadata.get("num_examples"))
        sequence_length = payload.get(
            "sequence_length",
            metadata.get("sequence_length"),
        )
        shard_payloads = payload.get("shards", ())
        return cls(
            artifact_kind=artifact_kind,
            schema_version=str(payload.get("schema_version", "0")),
            contract_package=str(payload.get("contract_package", CONTRACT_PACKAGE)),
            contract_version=str(payload.get("contract_version", CONTRACT_VERSION)),
            producer=str(payload.get("producer", "")),
            artifact_id=(
                None
                if payload.get("artifact_id") is None
                else str(payload.get("artifact_id"))
            ),
            role=role,
            payload_format=payload_format,
            vocab_contract=(
                None
                if vocab_payload is None
                else VocabContract.from_dict(vocab_payload)
            ),
            record_count=None if record_count is None else int(record_count),
            sequence_length=None if sequence_length is None else int(sequence_length),
            shard_count=int(payload.get("shard_count", len(shard_payloads) or 1)),
            shards=tuple(TomeShard.from_dict(dict(item)) for item in shard_payloads),
            metadata=metadata,
            provenance=dict(payload.get("provenance", {})),
        )


def _payload_format_from_payload(
    payload: dict[str, Any],
    metadata: dict[str, Any],
) -> TomePayloadFormat:
    raw = payload.get(
        "payload_format",
        metadata.get("payload_format", "dense_logits_v0"),
    )
    return TomePayloadFormat(str(raw))


def _role_from_payload(payload: dict[str, Any], metadata: dict[str, Any]) -> TomeRole:
    raw = payload.get("role", metadata.get("role", TomeRole.TRAINING.value))
    return TomeRole(str(raw))
