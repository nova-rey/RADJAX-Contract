from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from radjax_contract.tome.payloads import TomePayloadFormat, parse_tome_payload_format


class TomeCompressionFamily(StrEnum):
    NONE = "none"
    TOPK_WITH_TAIL = "topk_with_tail"
    CASCADED_BUCKETS = "cascaded_buckets"
    BEHAVIORAL_FINGERPRINT = "behavioral_fingerprint"
    DYNAMIC_TOPK_CASCADED_BUCKETS = "dynamic_topk_cascaded_buckets"


@dataclass(frozen=True)
class TomeCompression:
    family: TomeCompressionFamily = TomeCompressionFamily.NONE
    version: str = "0"
    lossless: bool = True
    requires_reconstruction: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family.value,
            "version": self.version,
            "lossless": self.lossless,
            "requires_reconstruction": self.requires_reconstruction,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TomeCompression:
        family = TomeCompressionFamily(str(payload.get("family", "")))
        return cls(
            family=family,
            version=str(payload.get("version", "0")),
            lossless=bool(
                payload.get("lossless", family is TomeCompressionFamily.NONE)
            ),
            requires_reconstruction=bool(payload.get("requires_reconstruction", False)),
            parameters=dict(payload.get("parameters", {})),
        )


PAYLOAD_COMPRESSION_FAMILIES: dict[TomePayloadFormat, TomeCompressionFamily] = {
    TomePayloadFormat.DENSE_LOGITS_V0: TomeCompressionFamily.NONE,
    TomePayloadFormat.TOPK_WITH_TAIL_V0: TomeCompressionFamily.TOPK_WITH_TAIL,
    TomePayloadFormat.CASCADED_SOFT_LABELS_V1: TomeCompressionFamily.CASCADED_BUCKETS,
    TomePayloadFormat.FINGERPRINT_CORRIDOR_V0: (
        TomeCompressionFamily.BEHAVIORAL_FINGERPRINT
    ),
    TomePayloadFormat.EXEMPLAR_RESERVOIR_V0: (
        TomeCompressionFamily.BEHAVIORAL_FINGERPRINT
    ),
    TomePayloadFormat.DYNAMIC_TOPK_CASCADED_BUCKETS_V0: (
        TomeCompressionFamily.DYNAMIC_TOPK_CASCADED_BUCKETS
    ),
}


def expected_compression_for_payload(
    payload_format: TomePayloadFormat | str,
) -> TomeCompressionFamily | None:
    parsed = (
        payload_format
        if isinstance(payload_format, TomePayloadFormat)
        else parse_tome_payload_format(payload_format)
    )
    if parsed is None:
        return None
    return PAYLOAD_COMPRESSION_FAMILIES.get(parsed)


def valid_compression_for_payload(
    payload_format: TomePayloadFormat | str,
    compression: TomeCompression | TomeCompressionFamily | str,
) -> bool:
    expected = expected_compression_for_payload(payload_format)
    if expected is None:
        return False
    if isinstance(compression, TomeCompression):
        family = compression.family
    elif isinstance(compression, TomeCompressionFamily):
        family = compression
    else:
        try:
            family = TomeCompressionFamily(str(compression))
        except ValueError:
            return False
    return family is expected
