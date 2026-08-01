"""Material delivery corpus for the native-v3 Student-consumption contract.

The test builder intentionally writes bytes to an isolated temporary corpus;
the checked-in manifest vectors pin the normative shape while this suite proves
the public resolver handles the three supported physical deliveries.
"""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

from test_tome_contract_publication import _canonical_tgz, _student_artifact

from radjax_contract.tome import validate_and_resolve_student_consumption


def _archive(root: Path, destination: Path) -> None:
    with tarfile.open(destination, "w") as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            archive.add(path, arcname=path.relative_to(root).as_posix())


def test_material_corpus_validates_directory_rtome_and_canonical_tgz(
    tmp_path: Path,
) -> None:
    directory = _student_artifact(tmp_path / "directory")
    assert validate_and_resolve_student_consumption(directory).ok

    cover_path = directory / "cover_page.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    cover["package"]["transport"] = "rtome"
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    rtome = tmp_path / "student.rtome"
    _archive(directory, rtome)
    assert validate_and_resolve_student_consumption(rtome).ok

    cover["package"]["transport"] = "tgz"
    cover_path.write_text(json.dumps(cover), encoding="utf-8")
    tgz = tmp_path / "student.tgz"
    _canonical_tgz(directory, tgz)
    assert validate_and_resolve_student_consumption(tgz, strict=True).ok
