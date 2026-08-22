from __future__ import annotations

from typing import Literal

from .models import Face


def discretize(
    samples: list[float],
    n_faces: int,
    strategy: Literal["equal_mass", "equal_width"] = "equal_mass",
) -> list[Face]:
    """Bin `samples` into `n_faces` weighted faces by the given strategy.

    `equal_mass` gives every face an equal share of the samples; `equal_width` gives
    every face an equal slice of the observed value range.
    """
    if n_faces < 1:
        raise ValueError("n_faces must be at least 1")
    if not samples:
        raise ValueError("samples must not be empty")

    if strategy == "equal_mass":
        return _discretize_equal_mass(samples, n_faces)
    if strategy == "equal_width":
        return _discretize_equal_width(samples, n_faces)
    raise ValueError(f"unknown strategy: {strategy!r}")


def _discretize_equal_mass(samples: list[float], n_faces: int) -> list[Face]:
    if n_faces > len(samples):
        raise ValueError("n_faces cannot exceed the number of samples for equal_mass binning")

    ordered = sorted(samples)
    total = len(ordered)
    base, remainder = divmod(total, n_faces)

    faces = []
    start = 0
    for i in range(n_faces):
        size = base + (1 if i < remainder else 0)
        chunk = ordered[start : start + size]
        start += size
        faces.append(
            Face(
                label=str(i + 1),
                weight=len(chunk) / total,
                value_range=(chunk[0], chunk[-1]),
            )
        )
    return faces


def _discretize_equal_width(samples: list[float], n_faces: int) -> list[Face]:
    lo, hi = min(samples), max(samples)
    if lo == hi:
        raise ValueError("samples have zero spread; equal_width binning needs a real range")

    total = len(samples)
    width = (hi - lo) / n_faces
    boundaries = [lo + i * width for i in range(n_faces + 1)]
    counts = [0] * n_faces
    for value in samples:
        idx = min(int((value - lo) / width), n_faces - 1)
        counts[idx] += 1

    return [
        Face(
            label=str(i + 1),
            weight=counts[i] / total,
            value_range=(boundaries[i], boundaries[i + 1]),
        )
        for i in range(n_faces)
    ]
