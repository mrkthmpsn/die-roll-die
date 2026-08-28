"""Covers the presentation logic in `examples/`, which the library's own tests do not import.

Two defects reached the shipped scripts through that gap: `_param_names` returned
`beta_binomial` as a parameter name after a rename, and `_summarise` had no
`gamma_exponential` branch, so an exponential prior printed its two parameters under the
`normal_normal` wording.
"""

from __future__ import annotations

import pytest

from die_scouting import POSTERIOR_PARAM_NAMES
from examples.fit import describe
from examples.roll import _summarise, parse_scope


@pytest.mark.parametrize("model", sorted(POSTERIOR_PARAM_NAMES))
def test_every_model_has_a_summary(model):
    assert _summarise(model, 4.0, 20.0, "goals", "appearances")


def test_an_unknown_model_raises_rather_than_borrowing_another_wording():
    with pytest.raises(ValueError, match="no summary"):
        _summarise("gamma_gamma", 4.0, 20.0, "goals", "appearances")


def test_a_count_model_reads_as_a_rate_over_its_denominator():
    summary = _summarise("gamma_poisson", 4.0, 20.0, "goals", "appearances")
    assert summary == "0.200 goals/appearances, worth 20.0 appearances of evidence"


def test_a_duration_model_divides_the_other_way_round():
    """`gamma_exponential` holds events in `alpha` and the time they took in `beta`, so the
    quantity is time per event and the evidence is the count of events."""
    summary = _summarise("gamma_exponential", 4.0, 20.0, "hours", "failures")
    assert summary == "5.000 hours/failures, worth 4.0 failures of evidence"


def test_a_proportion_model_reads_as_a_share_of_its_attempts():
    summary = _summarise("beta_binomial", 4.0, 20.0, "on_target", "shots")
    assert summary == "0.167 on_target/shots, worth 24.0 shots of evidence"


def test_parse_scope_reads_column_equals_value():
    assert parse_scope(["position_general=Forward", "season_name=2024/25"]) == {
        "position_general": "Forward",
        "season_name": "2024/25",
    }


def test_parse_scope_rejects_a_pair_with_no_value():
    with pytest.raises(SystemExit):
        parse_scope(["position_general"])


def test_describe_names_the_unscoped_prior():
    assert describe({}) == "global"
    assert describe({"position_general": "Forward"}) == "position_general=Forward"
