from pathlib import Path

from radjax_contract.provenance import file_sha256, stable_hash


def test_stable_hash_is_deterministic() -> None:
    left = {"b": [2, 1], "a": {"z": True}}
    right = {"a": {"z": True}, "b": [2, 1]}

    assert stable_hash(left) == stable_hash(right)


def test_file_sha256(tmp_path: Path) -> None:
    path = tmp_path / "payload.txt"
    path.write_text("radjax\n", encoding="utf-8")

    assert file_sha256(path) == file_sha256(path)
    assert len(file_sha256(path)) == 64
