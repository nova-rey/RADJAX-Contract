from radjax_contract.artifacts import ArtifactManifest, TeacherTomeManifest
from radjax_contract.vocab import VocabContract, validate_vocab_compatibility


def test_manifest_round_trips() -> None:
    manifest = TeacherTomeManifest(artifact_id="toy")
    round_tripped = ArtifactManifest.from_dict(manifest.to_dict())

    assert round_tripped.producer == "radjax-tome"
    assert round_tripped.schema_name == "teacher_tome_v0"
    assert round_tripped.artifact_id == "toy"


def test_vocab_compatibility() -> None:
    left = VocabContract(tokenizer_id="toy", vocab_size=8)
    right = VocabContract(tokenizer_id="toy", vocab_size=8)
    mismatch = VocabContract(tokenizer_id="other", vocab_size=8)

    assert validate_vocab_compatibility(left, right).ok is True
    assert validate_vocab_compatibility(left, mismatch).ok is False
