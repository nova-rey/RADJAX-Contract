from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TokenizerFingerprint:
    tokenizer_id: str
    tokenizer_hash: str | None = None
    vocab_size: int | None = None
    special_tokens: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "tokenizer_id": self.tokenizer_id,
            "tokenizer_hash": self.tokenizer_hash,
            "vocab_size": self.vocab_size,
            "special_tokens": dict(self.special_tokens),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> TokenizerFingerprint:
        return cls(
            tokenizer_id=str(payload["tokenizer_id"]),
            tokenizer_hash=(
                None
                if payload.get("tokenizer_hash") is None
                else str(payload["tokenizer_hash"])
            ),
            vocab_size=(
                None
                if payload.get("vocab_size") is None
                else int(payload["vocab_size"])
            ),
            special_tokens={
                str(key): int(value)
                for key, value in dict(payload.get("special_tokens", {})).items()
            },
        )


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

    def to_dict(self) -> dict[str, object]:
        return {
            "tokenizer_id": self.tokenizer_id,
            "vocab_size": self.vocab_size,
            "tokenizer_hash": self.tokenizer_hash,
            "model_id": self.model_id,
            "model_family": self.model_family,
            "special_tokens": dict(self.special_tokens),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> VocabContract:
        return cls(
            tokenizer_id=str(payload["tokenizer_id"]),
            vocab_size=int(payload["vocab_size"]),
            tokenizer_hash=(
                None
                if payload.get("tokenizer_hash") is None
                else str(payload["tokenizer_hash"])
            ),
            model_id=(
                None if payload.get("model_id") is None else str(payload["model_id"])
            ),
            model_family=(
                None
                if payload.get("model_family") is None
                else str(payload["model_family"])
            ),
            special_tokens={
                str(key): int(value)
                for key, value in dict(payload.get("special_tokens", {})).items()
            },
        )


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
