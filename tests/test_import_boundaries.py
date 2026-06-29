from pathlib import Path

FORBIDDEN = (
    "radjax_tome",
    "radjax_student",
    "torch",
    "transformers",
    "jax",
)


def test_contract_import_boundaries() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "radjax_contract"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for name in FORBIDDEN:
            if f"import {name}" in text or f"from {name}" in text:
                offenders.append(f"{path.relative_to(root)} imports {name}")

    assert offenders == []
