from __future__ import annotations

from typing import Any

from radjax_contract.provenance.hashes import stable_hash


def build_artifact_lineage(*, sources: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [dict(source) for source in sources]
    return {
        "sources": normalized,
        "lineage_hash": stable_hash(normalized),
    }
