"""Covers the presentation logic in `examples/`, which the library's own tests do not import.

That gap is how `_param_names` came to return `beta_binomial` as a parameter name after a
rename and reach the shipped scripts uncaught.
"""

from __future__ import annotations

import pytest

from die_scouting import POSTERIOR_PARAM_NAMES
from examples.fit_priors import describe
from examples.roll import _summarise, parse_scope


@pytest.mark.parametrize("model", sorted(POSTERIOR_PARAM_NAMES))
def test_every_model_has_a_summary(model):
    assert _summarise(model, 4.0, 20.0, "goals", "appearances")


def test_a_count_model_reads_as_a_rate_over_its_denominator():
    summary = _summarise("gamma_poisson", 4.0, 20.0, "goals", "appearances")
    assert summary == "0.200 goals/appearances, worth 20.0 appearances of evidence"


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
