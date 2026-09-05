"""Covers the presentation logic in `examples/`, which the library's own tests do not import.

Two defects reached the shipped scripts through that gap: `_param_names` returned
`beta_binomial` as a parameter name after a rename, and `_summarise` had no
`gamma_exponential` branch, so an exponential prior printed its two parameters under the
`normal_normal` wording.
"""

from __future__ import annotations

import pytest

from die_roll_die import POSTERIOR_PARAM_NAMES, JsonPriorStore, PriorParams
from examples.fit import describe
from examples.roll import _summarise, parse_scope, read_prior


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


def test_a_missing_prior_store_names_the_script_that_writes_one(tmp_path):
    """A fresh clone has no `data/priors.json`, `JsonPriorStore` reads a missing path as an
    empty store, and the message for a store lacking one scope would describe that as a fit
    that produced nothing."""
    with pytest.raises(SystemExit) as exit_info:
        read_prior(tmp_path / "priors.json", "player", "goals", {})
    message = str(exit_info.value)
    assert "no prior store at" in message
    assert "examples/fit.py" in message


def test_a_store_lacking_the_scope_lists_the_scopes_it_holds(tmp_path):
    path = tmp_path / "priors.json"
    store = JsonPriorStore(path)
    store.save(
        PriorParams(
            stat_id="goals",
            entity_type="player",
            scope={"position_general": "Forward"},
            model="gamma_poisson",
            params={"alpha": 2.0, "beta": 11.0},
        )
    )
    with pytest.raises(SystemExit) as exit_info:
        read_prior(path, "player", "goals", {"position_general": "Goalkeeper"})
    message = str(exit_info.value)
    assert "holds no prior for 'goals'" in message
    assert "position_general" in message and "Forward" in message
