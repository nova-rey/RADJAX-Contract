from __future__ import annotations

from pathlib import Path

import numpy as np


def load_array(path: str | Path) -> np.ndarray:
    return np.load(Path(path), allow_pickle=False)


def save_array(path: str | Path, value: np.ndarray) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    np.save(target, value, allow_pickle=False)
