from __future__ import annotations

from pathlib import Path

from radjax_contract.validation._result import ValidationResult


def validate_target_store(path: str | Path) -> ValidationResult:
    return ValidationResult(ok=Path(path).exists())
