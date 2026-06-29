from __future__ import annotations

from enum import StrEnum


class TomePayloadFormat(StrEnum):
    DENSE_LOGITS_V0 = "dense_logits_v0"
    TOPK_WITH_TAIL_V0 = "topk_with_tail_v0"
    CASCADED_SOFT_LABELS_V1 = "cascaded_soft_labels_v1"
    DYNAMIC_TOPK_CASCADED_BUCKETS_V0 = "dynamic_topk_cascaded_buckets_v0"
    FINGERPRINT_CORRIDOR_V0 = "fingerprint_corridor_v0"
    EXEMPLAR_RESERVOIR_V0 = "exemplar_reservoir_v0"


IMPLEMENTED_TOME_PAYLOAD_FORMATS = frozenset({TomePayloadFormat.DENSE_LOGITS_V0})
DEFAULT_DENSE_LOGITS_PAYLOAD = "logits.npy"


def parse_tome_payload_format(value: object) -> TomePayloadFormat | None:
    try:
        return TomePayloadFormat(str(value))
    except ValueError:
        return None
