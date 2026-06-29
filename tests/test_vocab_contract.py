from pytest import raises

from radjax_contract.vocab import (
    TokenizerFingerprint,
    VocabContract,
    validate_vocab_compatibility,
)


def test_vocab_contract_round_trip_works() -> None:
    contract = VocabContract(
        tokenizer_id="toy",
        vocab_size=8,
        tokenizer_hash="abc",
        model_id="teacher",
        model_family="fake",
        special_tokens={"eos": 1},
    )

    assert VocabContract.from_dict(contract.to_dict()) == contract


def test_tokenizer_fingerprint_round_trip_works() -> None:
    fingerprint = TokenizerFingerprint(
        tokenizer_id="toy",
        tokenizer_hash="abc",
        vocab_size=8,
        special_tokens={"eos": 1},
    )

    assert TokenizerFingerprint.from_dict(fingerprint.to_dict()) == fingerprint


def test_vocab_contract_rejects_non_positive_vocab() -> None:
    with raises(ValueError, match="vocab_size"):
        VocabContract(tokenizer_id="toy", vocab_size=0)


def test_vocab_mismatch_produces_blockers() -> None:
    left = VocabContract(tokenizer_id="toy", vocab_size=8, tokenizer_hash="a")
    right = VocabContract(tokenizer_id="other", vocab_size=9, tokenizer_hash="b")

    result = validate_vocab_compatibility(left, right)

    assert result.ok is False
    assert "tokenizer_id mismatch" in result.blockers
    assert "vocab_size mismatch" in result.blockers
    assert "tokenizer_hash mismatch" in result.blockers


def test_vocab_hash_mismatch_only_blocks_when_both_present() -> None:
    left = VocabContract(tokenizer_id="toy", vocab_size=8, tokenizer_hash="a")
    right = VocabContract(tokenizer_id="toy", vocab_size=8)

    assert validate_vocab_compatibility(left, right).ok is True
