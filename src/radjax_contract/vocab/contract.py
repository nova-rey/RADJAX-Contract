from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TokenizerFingerprint:
    tokenizer_id: str
    tokenizer_hash: str | None = None
    vocab_size: int | None = None
    special_tokens: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class VocabContract:
    tokenizer_id: str
    vocab_size: int
    tokenizer_hash: str | None = None
    model_id: str | None = None
    model_family: str | None = None
    special_tokens: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.vocab_size <= 0:
            raise ValueError("vocab_size must be > 0")


@dataclass(frozen=True)
class VocabCompatibilityResult:
    ok: bool
    blockers: tuple[str, ...] = ()


def validate_vocab_compatibility(
    left: VocabContract,
    right: VocabContract,
) -> VocabCompatibilityResult:
    blockers: list[str] = []
    if left.tokenizer_id != right.tokenizer_id:
        blockers.append("tokenizer_id mismatch")
    if left.vocab_size != right.vocab_size:
        blockers.append("vocab_size mismatch")
    if (
        left.tokenizer_hash is not None
        and right.tokenizer_hash is not None
        and left.tokenizer_hash != right.tokenizer_hash
    ):
        blockers.append("tokenizer_hash mismatch")
    return VocabCompatibilityResult(ok=not blockers, blockers=tuple(blockers))
