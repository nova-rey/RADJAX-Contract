from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_file_sha256(path: str | Path) -> str:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return stable_hash(payload)


def records_identity_hash(records: list[dict[str, Any]]) -> str:
    identities = []
    for record in records:
        identities.append(
            {
                "example_id": record.get("example_id"),
                "token_ids_sha256": record.get("token_ids_sha256"),
                "source_sha256": record.get("source_sha256"),
                "text": record.get("text"),
            }
        )
    return stable_hash(identities)
