from __future__ import annotations

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
    faces = discretize(samples, n_faces=5, strategy="equal_width")
    assert len(faces) == 5
    assert sum(f.weight for f in faces) == pytest.approx(1.0)


def test_equal_width_bins_are_equal_size():
    samples = [0.0, 10.0, 5.0]
    faces = discretize(samples, n_faces=5, strategy="equal_width")
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
