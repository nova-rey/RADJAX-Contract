"""Installed final v3 Contract asset discovery and checksum pinning."""

from __future__ import annotations

import hashlib
from pathlib import Path

from radjax_contract.tome.contract_publication import tome_artifact_v3_contract_root
from radjax_contract.tome.v3.issues import TomeV3ValidationError, ValidationPhaseV3


def contract_root() -> Path:
    return tome_artifact_v3_contract_root()


def asset_path(relative_path: str) -> Path:
    root = contract_root()
    candidate = root / relative_path
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise TomeV3ValidationError(
            "contract_asset_path_unsafe", phase=ValidationPhaseV3.DISPATCH
        ) from exc
    if not candidate.is_file():
        raise TomeV3ValidationError(
            "contract_asset_missing",
            phase=ValidationPhaseV3.DISPATCH,
            location=relative_path,
        )
    return candidate


def verify_asset_checksums() -> None:
    """Verify the installed v3 static Contract asset tree against SHA256SUMS."""

    manifest = asset_path("SHA256SUMS")
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        member = asset_path(relative)
        actual = hashlib.sha256(member.read_bytes()).hexdigest()
        if actual != digest:
            raise TomeV3ValidationError(
                "contract_asset_checksum_mismatch",
                phase=ValidationPhaseV3.DISPATCH,
                location=relative,
            )
