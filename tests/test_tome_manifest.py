from radjax_contract.tome import (
    TomeManifest,
    TomePayloadFormat,
    TomeRole,
    TomeShard,
)
from radjax_contract.vocab import VocabContract


def test_tome_manifest_round_trips() -> None:
    manifest = TomeManifest(
        artifact_id="abc",
        role=TomeRole.CALIBRATION,
        payload_format=TomePayloadFormat.DENSE_LOGITS_V0,
        vocab_contract=VocabContract(tokenizer_id="toy", vocab_size=7),
        record_count=2,
        sequence_length=4,
        shard_count=1,
        shards=(TomeShard(path="logits.npy", record_count=2),),
    )

    round_tripped = TomeManifest.from_dict(manifest.to_dict())

    assert round_tripped == manifest


def test_tome_manifest_accepts_current_tome_scaffold_shape() -> None:
    payload = {
        "producer": "radjax-tome",
        "schema_name": "teacher_tome_v0",
        "schema_version": "0",
        "contract_package": "radjax-contract",
        "metadata": {
            "num_examples": 3,
            "sequence_length": 5,
            "vocab_size": 11,
        },
    }

    manifest = TomeManifest.from_dict(payload)

    assert manifest.artifact_kind == "radjax_tome"
    assert manifest.record_count == 3
    assert manifest.sequence_length == 5
    assert manifest.payload_format is TomePayloadFormat.DENSE_LOGITS_V0
