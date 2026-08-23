from __future__ import annotations

from typing import Any, Literal

from .discretizer import discretize
from .models import Die


def build_die(
    samples: list[float],
    n_faces: int = 6,
    metadata: dict[str, Any] | None = None,
    strategy: Literal["equal_mass", "equal_width"] = "equal_mass",
) -> Die:
    """Discretize `samples` into `n_faces` faces by `strategy` and wrap them in a `Die`."""
    faces = discretize(samples, n_faces, strategy)
    return Die(faces=faces, metadata=metadata or {})
