from __future__ import annotations

from typing import Literal

from .models import Face


def discretize(
    samples: list[float],
    n_faces: int,
    strategy: Literal["equal_mass", "equal_width"] = "equal_mass",
) -> list[Face]:
    """Bin a sample array into weighted die faces. Pure stats, no domain knowledge —
    doesn't know or care whether the samples came from an AnalyticSource or a
    BootstrapSource.
    """
    raise NotImplementedError
