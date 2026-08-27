from __future__ import annotations

from typing import Literal

from .discretizer import discretize
from .models import Die, DieMetadata


def build_die(
    samples: list[float],
    n_faces: int = 6,
    metadata: DieMetadata | None = None,
    strategy: Literal["equal_weight", "equal_width"] = "equal_width",
) -> Die:
    """Discretize `samples` into `n_faces` faces by `strategy` and wrap them in a `Die`.

    The returned die's metadata is `metadata` with `strategy` and `draws` set from this
    call, `draws` being the number of samples given before any were clipped.
    """
    faces = discretize(samples, n_faces, strategy)
    stamped = (metadata or DieMetadata()).model_copy(
        update={"strategy": strategy, "draws": len(samples)}
    )
    return Die(faces=faces, metadata=stamped)
