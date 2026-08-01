"""Resource discovery for the released RADJAX-Tome portable contract."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

TOME_CONTRACT_ID = "radjax_tome_artifact_contract"
TOME_CONTRACT_PUBLICATION_VERSION = "1.0.0"
TOME_STREAMING_CONTRACT_PUBLICATION_VERSION = "2.0.0"
TOME_STUDENT_CONSUMPTION_CONTRACT_ID = "radjax_tome_student_consumption_contract"
TOME_STUDENT_CONSUMPTION_CONTRACT_PUBLICATION_VERSION = "1.0.0"
TOME_STUDENT_CONSUMPTION_V2_CONTRACT_PUBLICATION_VERSION = "2.0.0"


def tome_contract_root() -> Path:
    """Return the installed, versioned Tome contract resource directory."""

    root = files("radjax_contract").joinpath("contracts", "radjax_tome", "v1")
    return Path(str(root))


def tome_contract_asset_path(relative_path: str) -> Path:
    """Return one contract asset after rejecting traversal-like names."""

    if (
        not relative_path
        or relative_path.startswith("/")
        or ".." in relative_path.split("/")
    ):
        raise ValueError("contract asset path must be a normalized relative path")
    asset = tome_contract_root() / relative_path
    if not asset.is_file():
        raise ValueError(f"unknown Tome contract asset: {relative_path}")
    return asset


def tome_streaming_contract_root() -> Path:
    """Return the installed M7 v4 streaming-contract resource directory."""

    root = files("radjax_contract").joinpath("contracts", "radjax_tome", "v2")
    return Path(str(root))


def tome_streaming_contract_asset_path(relative_path: str) -> Path:
    """Return one M7 streaming asset after rejecting traversal-like names."""

    if (
        not relative_path
        or relative_path.startswith("/")
        or ".." in relative_path.split("/")
    ):
        raise ValueError("contract asset path must be a normalized relative path")
    asset = tome_streaming_contract_root() / relative_path
    if not asset.is_file():
        raise ValueError(f"unknown streaming Tome contract asset: {relative_path}")
    return asset


def tome_student_consumption_contract_root() -> Path:
    """Return the installed native-v3 Student-consumption contract assets."""

    root = files("radjax_contract").joinpath(
        "contracts", "radjax_tome", "student_consumption", "v1"
    )
    return Path(str(root))


def tome_student_consumption_contract_asset_path(relative_path: str) -> Path:
    """Return one native-v3 Student-consumption asset safely."""

    if (
        not relative_path
        or relative_path.startswith("/")
        or ".." in relative_path.split("/")
    ):
        raise ValueError("contract asset path must be a normalized relative path")
    asset = tome_student_consumption_contract_root() / relative_path
    if not asset.is_file():
        raise ValueError(f"unknown Student-consumption contract asset: {relative_path}")
    return asset


def tome_student_consumption_v2_contract_root() -> Path:
    """Return installed v2 native-v3 Student-consumption contract assets."""

    root = files("radjax_contract").joinpath(
        "contracts", "radjax_tome", "student_consumption", "v2"
    )
    return Path(str(root))


def tome_student_consumption_v2_contract_asset_path(relative_path: str) -> Path:
    """Return one v2 Student-consumption asset after safe path validation."""

    if (
        not relative_path
        or relative_path.startswith("/")
        or ".." in relative_path.split("/")
    ):
        raise ValueError("contract asset path must be a normalized relative path")
    asset = tome_student_consumption_v2_contract_root() / relative_path
    if not asset.is_file():
        raise ValueError(
            f"unknown v2 Student-consumption contract asset: {relative_path}"
        )
    return asset


__all__ = [
    "TOME_CONTRACT_ID",
    "TOME_CONTRACT_PUBLICATION_VERSION",
    "TOME_STREAMING_CONTRACT_PUBLICATION_VERSION",
    "TOME_STUDENT_CONSUMPTION_CONTRACT_ID",
    "TOME_STUDENT_CONSUMPTION_CONTRACT_PUBLICATION_VERSION",
    "TOME_STUDENT_CONSUMPTION_V2_CONTRACT_PUBLICATION_VERSION",
    "tome_contract_asset_path",
    "tome_contract_root",
    "tome_streaming_contract_asset_path",
    "tome_streaming_contract_root",
    "tome_student_consumption_contract_asset_path",
    "tome_student_consumption_contract_root",
    "tome_student_consumption_v2_contract_asset_path",
    "tome_student_consumption_v2_contract_root",
]
