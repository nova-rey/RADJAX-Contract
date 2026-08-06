"""Duplicate-rejecting, lexeme-preserving JSON/JSONL decoding for v3.

The normal Contract JSON helpers intentionally preserve historic permissive
behaviour.  This module is separate because semantic v3 numbers must be
selected by the closed profile, never by a host JSON parser's float coercion.
"""

from __future__ import annotations

import json
from typing import Any

from radjax_contract.tome.v3.issues import TomeV3ValidationError, ValidationPhaseV3


class NumberLexeme(str):
    """A JSON numeric token retained until the field schema chooses its type."""


def _reject_duplicates(
    pairs: list[tuple[str, Any]], *, phase: ValidationPhaseV3
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TomeV3ValidationError("duplicate_json_key", phase=phase)
        result[key] = value
    return result


def loads(text: str, *, phase: ValidationPhaseV3 = ValidationPhaseV3.DISPATCH) -> Any:
    """Load one JSON value with duplicate keys and nonstandard constants rejected."""

    def invalid_constant(value: str) -> Any:
        raise TomeV3ValidationError("json_nonfinite", phase=phase)

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        return _reject_duplicates(pairs, phase=phase)

    try:
        return json.loads(
            text,
            parse_int=NumberLexeme,
            parse_float=NumberLexeme,
            parse_constant=invalid_constant,
            object_pairs_hook=reject_duplicates,
        )
    except TomeV3ValidationError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TomeV3ValidationError("malformed_json", phase=phase) from exc


def load_jsonl(
    raw: bytes, *, phase: ValidationPhaseV3 = ValidationPhaseV3.SEMANTIC_RECORDS
) -> list[Any]:
    """Decode canonical v3 JSONL: UTF-8, no blank rows, final LF required."""

    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise TomeV3ValidationError("jsonl_not_utf8", phase=phase) from exc
    if not text.endswith("\n"):
        raise TomeV3ValidationError("jsonl_missing_final_newline", phase=phase)
    lines = text[:-1].split("\n")
    if any(line == "" for line in lines):
        raise TomeV3ValidationError("jsonl_blank_line", phase=phase)
    return [loads(line, phase=phase) for line in lines] if lines else []
