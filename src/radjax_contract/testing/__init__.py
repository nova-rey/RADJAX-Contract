from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def production_tome_fixture_path() -> Path:
    """Return the packaged P1.5 production-shaped Tome artifact."""

    fixture = files("radjax_contract.testing").joinpath(
        "fixtures",
        "production_multi_surface_v1",
        "artifact",
    )
    return Path(str(fixture))


__all__ = ["production_tome_fixture_path"]
