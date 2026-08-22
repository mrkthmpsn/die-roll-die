from __future__ import annotations

import numpy as np
import pytest

from die_scouting import discretize


def test_equal_mass_face_count_and_weight_sum():
    samples = list(range(100))
    faces = discretize(samples, n_faces=6, strategy="equal_mass")
    assert len(faces) == 6
    assert sum(f.weight for f in faces) == pytest.approx(1.0)


def test_equal_mass_supports_d20():
    samples = list(range(1000))
    faces = discretize(samples, n_faces=20, strategy="equal_mass")
    assert len(faces) == 20
    assert sum(f.weight for f in faces) == pytest.approx(1.0)


def test_equal_mass_bins_are_ordered_and_contiguous():
    samples = [float(i) for i in range(60)]
    faces = discretize(samples, n_faces=6, strategy="equal_mass")
    for earlier, later in zip(faces, faces[1:]):
        assert earlier.value_range[1] <= later.value_range[0]


def test_equal_width_face_count_and_weight_sum():
    samples = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 9.0, 9.5]
    faces = discretize(samples, n_faces=5, strategy="equal_width", clip=None)
    assert len(faces) == 5
    assert sum(f.weight for f in faces) == pytest.approx(1.0)


def test_equal_width_bins_are_equal_size():
    samples = [0.0, 10.0, 5.0]
    faces = discretize(samples, n_faces=5, strategy="equal_width", clip=None)
    widths = [f.value_range[1] - f.value_range[0] for f in faces]
    assert all(w == pytest.approx(widths[0]) for w in widths)


def test_rejects_empty_samples():
    with pytest.raises(ValueError):
        discretize([], n_faces=6)


def test_rejects_zero_or_negative_faces():
    with pytest.raises(ValueError):
        discretize([1.0, 2.0], n_faces=0)


def test_equal_mass_rejects_more_faces_than_samples():
    with pytest.raises(ValueError):
        discretize([1.0, 2.0], n_faces=6, strategy="equal_mass")


def test_equal_width_rejects_zero_spread_samples():
    with pytest.raises(ValueError):
        discretize([5.0, 5.0, 5.0], n_faces=6, strategy="equal_width")


def test_unknown_strategy_rejected():
    with pytest.raises(ValueError):
        discretize([1.0, 2.0, 3.0], n_faces=2, strategy="not_a_strategy")


def test_clipping_makes_the_top_face_stable_across_sample_sizes():
    """Unclipped, the top face reports the most extreme draw, so its bound climbs with
    the number of samples taken rather than describing the distribution.
    """
    rng = np.random.default_rng(1)
    bounds = []
    for n in (10_000, 500_000):
        samples = rng.poisson(rng.gamma(3.0, 1 / 10.0, n) * 30.0).astype(float).tolist()
        bounds.append(discretize(samples, n_faces=6)[-1].value_range[1])
    assert bounds[0] == pytest.approx(bounds[1], abs=2.0)


def test_clipping_drops_the_extremes_at_both_ends():
    samples = [-1000.0] + [float(i) for i in range(100)] + [1000.0]
    faces = discretize(samples, n_faces=6)
    assert faces[0].value_range[0] > -1000.0
    assert faces[-1].value_range[1] < 1000.0


def test_clip_none_keeps_the_extremes():
    samples = [-1000.0] + [float(i) for i in range(100)] + [1000.0]
    faces = discretize(samples, n_faces=6, clip=None)
    assert faces[0].value_range[0] == -1000.0
    assert faces[-1].value_range[1] == 1000.0


def test_weights_still_sum_to_one_after_clipping():
    samples = [float(i) for i in range(1000)]
    faces = discretize(samples, n_faces=6)
    assert sum(f.weight for f in faces) == pytest.approx(1.0)


def test_rejects_clip_quantiles_out_of_order():
    with pytest.raises(ValueError, match="clip quantiles"):
        discretize([1.0, 2.0, 3.0], n_faces=2, clip=(0.9, 0.1))
