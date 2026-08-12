from __future__ import annotations

from typing import Any

from .discretizer import discretize
from .models import Die


def build_die(
    samples: list[float], n_faces: int = 6, metadata: dict[str, Any] | None = None
) -> Die:
    """Assembles the final Die contract handed to a frontend roller. Pure wiring —
    everything statistical already happened upstream in `discretize`.
    """
    faces = discretize(samples, n_faces)
    return Die(faces=faces, metadata=metadata or {})
