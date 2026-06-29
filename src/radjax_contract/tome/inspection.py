from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from radjax_contract.tome.compression import (
    TomeCompression,
    expected_compression_for_payload,
    valid_compression_for_payload,
)
from radjax_contract.tome.cover_page import load_tome_cover_page
from radjax_contract.tome.payloads import (
    IMPLEMENTED_TOME_PAYLOAD_FORMATS,
    TomePayloadFormat,
)


@dataclass(frozen=True)
class TomeConsumptionPlan:
    payload_format: TomePayloadFormat | None
    compression: TomeCompression | None
    adapter_id: str | None
    implemented: bool
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


ADAPTER_IDS: dict[TomePayloadFormat, str] = {
    TomePayloadFormat.DENSE_LOGITS_V0: "dense_logits",
    TomePayloadFormat.TOPK_WITH_TAIL_V0: "topk_with_tail",
    TomePayloadFormat.CASCADED_SOFT_LABELS_V1: "cascaded_buckets",
    TomePayloadFormat.FINGERPRINT_CORRIDOR_V0: "fingerprint_corridor",
    TomePayloadFormat.EXEMPLAR_RESERVOIR_V0: "exemplar_reservoir",
    TomePayloadFormat.DYNAMIC_TOPK_CASCADED_BUCKETS_V0: (
        "dynamic_topk_cascaded_buckets"
    ),
}


def expected_adapter_for_payload(payload_format: TomePayloadFormat) -> str:
    return ADAPTER_IDS[payload_format]


def inspect_tome_for_consumption(path: str | Path) -> TomeConsumptionPlan:
    load_result = load_tome_cover_page(path)
    if load_result.cover_page is None:
        return TomeConsumptionPlan(
            payload_format=None,
            compression=None,
            adapter_id=None,
            implemented=False,
            blockers=load_result.blockers,
        )

    contents = load_result.cover_page.contents
    payload_format = contents.payload_format
    compression = contents.compression
    adapter_id = ADAPTER_IDS.get(payload_format)
    blockers = list(load_result.blockers)
    expected = expected_compression_for_payload(payload_format)
    if expected is None or not valid_compression_for_payload(
        payload_format, compression
    ):
        blockers.append(
            "compression_payload_mismatch: "
            f"payload_format={payload_format.value} "
            f"compression={compression.family.value} "
            f"expected={None if expected is None else expected.value}"
        )
    if adapter_id is None:
        blockers.append(f"adapter_unknown: {payload_format.value}")
    implemented = (
        not blockers
        and payload_format in IMPLEMENTED_TOME_PAYLOAD_FORMATS
        and adapter_id is not None
    )
    return TomeConsumptionPlan(
        payload_format=payload_format,
        compression=compression,
        adapter_id=adapter_id,
        implemented=implemented,
        blockers=tuple(blockers),
    )
