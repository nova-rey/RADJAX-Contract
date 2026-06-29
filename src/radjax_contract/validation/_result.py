from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    blockers: tuple[str, ...] = ()
