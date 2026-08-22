# die-scouting

Turn a Bayesian estimate of "quality" (a stat, or a pre-computed score for a specific role) into a weighted die, and roll it — a small illustrative tool for visualizing uncertainty in player-quality estimates.

## Status

Module skeleton scaffolded — data models and stubbed interfaces are in place for every module below (`die_scouting/`), verified with a smoke test (`tests/test_imports.py`). `Discretizer` and `AnalyticSource`'s gamma path are implemented; `PriorDiscovery`, `PriorStore.resolve_prior` and `BootstrapSource` still raise `NotImplementedError`, and no concrete `DataAdapter` exists yet.

## Development

```
uv venv
uv pip install -e ".[dev]"
.venv/Scripts/pytest tests/
```

## Core idea

Any value for a player (a raw stat like goals, or an externally-modeled score like "inverted full-back suitability out of 10") is treated as a stream of observations, each pairing a value with the exposure it accumulated over — twelve goals across thirty nineties, say. Bayesian updating turns "prior belief + this player's own record" into a posterior distribution over their true quality. That posterior gets discretized into weighted die faces and rolled.

The exposure denominator is what makes the die worth looking at: four goals in ten appearances and forty in a hundred imply the same rate, and only the second is evidence you can lean on. Two questions can be asked of the posterior — what the player's underlying rate is, and how many they would record over a stated amount of future playing time.

## Modules

**DataAdapter** — the only provider/domain-aware module. Supplies per-match values for one player, and population-wide values across many players (for prior discovery). Everything else is domain-agnostic.

**PriorDiscovery** (offline, periodic) — empirical Bayes: fits a prior distribution's parameters from the population-wide spread of a stat, rather than requiring someone to hand-pick numbers. Family selection is a small heuristic by stat type (Beta for bounded rates/proportions, Gamma for non-negative counts/rates, Normal for symmetric continuous values), fit via method of moments.

Scope is optional and composable — a prior can be global, or narrowed by any combination of dimensions (e.g. position group, competition). Stored as `PriorParams` keyed by `(stat_id, scope)`. Read-time lookup falls back to a broader/global scope if nothing's been discovered yet for a narrow slice.

**QualitySource** (online, per player/roll) — uniform interface: `sample(entity_id, n_draws) -> float[]`, returning draws of the player's underlying rate. Two implementations behind it:

- `AnalyticSource` — closed-form posterior (conjugate update of the discovered prior with this player's own observations). The gamma family is implemented as a Gamma-Poisson update, summing the observations' values and exposures onto the prior's `alpha` and `beta`. It also offers `sample_predictive(entity_id, n_draws, exposure)`, which draws a rate and then a Poisson count at that rate over the given exposure, so the die is over goals-next-season rather than goals-per-ninety. That exposure is supplied by the caller and held fixed, so the answer is "if they play thirty nineties" rather than "next season" — playing time is not itself modelled.
- `BootstrapSource` — resample this player's own match records with replacement, recompute, repeat — no named distribution family required

Reads the relevant `PriorParams` as config; never invokes `PriorDiscovery` itself.

**Discretizer** — pure stats, no domain knowledge: bins a sample array into weighted die faces (`{label, weight, value_range}`), by equal-mass or equal-width bin strategy. The face count is caller-chosen, so the same sample array can produce a D6, a D20, or any other die.

Implemented. `equal_mass` splits sorted samples into evenly-sized chunks, so every face carries roughly equal probability and the faces differ in how wide a value range they cover. `equal_width` splits the observed range into fixed-width bins, so the faces differ in weight instead.

Samples outside the 1st and 99th percentiles are dropped before binning, by default. Without that, an outer face reports the single most extreme draw as its bound — a die over predicted goals showed a top face of `14-73` where that outcome had probability 2e-6, and the bound climbed from 46 to 73 as the draw count went from a thousand to half a million. Clipping is skipped where the sample count is too small for the tails to hold a whole sample, so the default applies from a hundred samples upward. Pass `clip=None` to bin every sample.

**Die** — the contract handed to a frontend: `{faces, metadata}`. The rolling UI never touches raw stats, priors, or resampling.

## Pipeline

```
Offline (periodic):
  DataAdapter (population-wide) -> PriorDiscovery -> PriorParams (stored, keyed by stat + scope)

Online (per player, per roll):
  PriorParams + DataAdapter (per-player) -> QualitySource -> Discretizer -> Die
```

## Explicitly deferred / out of scope for now

- How a per-match "modeled score" (e.g. combining tackles, pass success, halfspace receptions into a role-suitability number) actually gets computed. Assume it already exists as an input value per match.
- A `Combinator` module that combines separately-drawn samples from multiple stats — considered and dropped. If a composite value is ever built by combining raw features, that belongs upstream of the Bayesian layer (as a pre-computed value per match), not as a distribution-combination step downstream of it.

## Possible data source

[empty-head-data](../empty-head-data) (sibling repo) exposes StatsBomb-derived football data via a Core REST API, including a `PlayerTeamSeasonStat` aggregate table and an 8-group position classification (`core/stats/positions.py`) that would make a natural first `DataAdapter` and a natural first "position group" prior scope.

Season aggregates are the right grain, not a compromise forced by what happens to be pre-computed: a Poisson update depends only on total count and total exposure, so a player's five seasons and the hundred-odd matches inside them produce an identical posterior. Collecting season totals is the cheaper route to the same answer.
