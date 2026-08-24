# die-scouting

Turn a Bayesian estimate of "quality" (a stat, or a pre-computed score for a specific role) into a weighted die, and roll it — a small illustrative tool for visualizing uncertainty in player-quality estimates.

## Status

The pipeline runs end to end on real data: `CsvDataAdapter` reads the Premier League extract in [data/](data/), `PriorDiscovery` fits a prior from it, and `PosteriorSampler` updates that prior for one player and feeds `Discretizer`. [examples/roll.py](examples/roll.py) does all of it for a named player and any stat.

`PriorStore.resolve_prior` and `BootstrapSampler` still raise `NotImplementedError`. All three prior families are implemented in `fit_prior` and `PosteriorSampler`.

```
uv run python examples/roll.py "Harry Kane" --scope position_general=Forward
```

## Development

```
uv sync
uv run pytest
```

## Core idea

Any value for a player (a raw stat like goals, or an externally-modeled score like "inverted full-back suitability out of 10") is treated as a stream of observations, each pairing a value with the denominator it accumulated over — twelve goals across thirty nineties, say. Bayesian updating turns "prior belief + this player's own record" into a posterior distribution over their true quality. That posterior gets discretized into weighted die faces and rolled.

The denominator denominator is what makes the die worth looking at: four goals in ten appearances and forty in a hundred imply the same rate, and only the second is evidence you can lean on. Two questions can be asked of the posterior — what the player's underlying rate is, and how many they would record over a stated amount of future playing time.

## Modules

**DataAdapter** — the only provider/domain-aware module. Supplies per-observation values for one player, and population-wide values across many players (for prior discovery). Everything else is domain-agnostic.

`CsvDataAdapter` implements it over a player-season CSV, reading any numeric column as the stat and any column as a scope filter, so the same class serves both the goals example and a future modelled score.

**PriorDiscovery** (offline, periodic) — empirical Bayes: fits a prior distribution's parameters from the population-wide spread of a stat, rather than requiring someone to hand-pick numbers. The distribution family is supplied by the caller rather than chosen from the stat's name — Beta for proportions bounded by 0 and 1, Gamma for positive quantities with no ceiling, Normal for values that can sit anywhere. The family states which values the stat can take at all, and no sample establishes that, because an unobserved value and an impossible one look identical in data; the parameters are then fitted from the population by method of moments. All three are implemented.

Each family corrects for the noise in its own inputs, and where that noise comes from differs. A Poisson's spread is fixed by its mean and a binomial's by its mean and its attempts, so both can be calculated and subtracted; a normal's is free, so `fit_prior` estimates it by pooling how much each entity's observations vary around that entity's own mean, which needs entities appearing more than once and is stored as the prior's third parameter, `sigma_obs`.

The gamma fit corrects for the noise in its own inputs. A season's goals-per-ninety is spread both by how much players genuinely differ and by the randomness of scoring itself, the second contributing `mean / denominator` to the variance of an observed rate; subtracting its average leaves the spread a prior should carry. Over the 1,721 forward-seasons of five or more nineties in this extract, more than half the apparent spread is that randomness, and correcting for it takes the prior from 7.6 to 16.6 nineties' worth of evidence — the difference between a player with three goals in four nineties reading as a genuine 0.6-per-90 striker or not. Seasons under five nineties are excluded from the fit outright, their rates being dominated by the small denominator.

Scope is optional and composable — a prior can be global, or narrowed by any combination of dimensions (e.g. position group, competition). Stored as `PriorParams` keyed by `(stat_id, scope)`. Read-time lookup falls back to a broader/global scope if nothing's been discovered yet for a narrow slice.

**QualitySampler** (online, per player/roll) — uniform interface: `sample(entity_id, n_draws) -> float[]`, returning draws of the player's underlying rate. Two implementations behind it:

- `PosteriorSampler` — closed-form posterior (conjugate update of the discovered prior with this player's own observations). Gamma updates as Gamma-Poisson, summing values and denominators onto `alpha` and `beta`; beta updates as Beta-Binomial, summing successes onto `alpha` and misses onto `beta`; normal updates by precision-weighting the prior's mean against the observations. It also offers `sample_predictive(entity_id, n_draws, denominator)`, which draws the player's underlying quality and then what they would record over the given denominator — a Poisson count for gamma, binomial successes for beta, a summed value for normal — so the die is over goals-next-season rather than goals-per-ninety. That denominator is supplied by the caller and held fixed, so the answer is "if they play thirty nineties" rather than "next season" — playing time is not itself modelled.
- `BootstrapSampler` — resample this player's own match records with replacement, recompute, repeat — no named distribution family required

Reads the relevant `PriorParams` as config; never invokes `PriorDiscovery` itself.

**Discretizer** — pure stats, no domain knowledge: bins a sample array into weighted die faces (`{label, weight, value_range}`), by equal-mass or equal-width bin strategy. The face count is caller-chosen, so the same sample array can produce a D6, a D20, or any other die.

Implemented. `equal_mass` splits sorted samples into evenly-sized chunks, so every face carries roughly equal probability and the faces differ in how wide a value range they cover. `equal_width` splits the observed range into fixed-width bins, so the faces differ in weight instead.

On whole-number samples, adjacent `equal_mass` faces can report the same integer as their bounds — a D20 over predicted goals showed faces of `21`, `21-22` and `22`, so 22 goals is an outcome on three faces of twenty. That is the die being honest about a count distribution having fewer distinct values than it has faces, and the weights stay correct.

Samples outside the 1st and 99th percentiles are dropped before binning, by default. Without that, an outer face reports the single most extreme draw as its bound — a die over predicted goals showed a top face of `14-73` where that outcome had probability 2e-6, and the bound climbed from 46 to 73 as the draw count went from a thousand to half a million. Clipping is skipped where the sample count is too small for the tails to hold a whole sample, so the default applies from a hundred samples upward. Pass `clip=None` to bin every sample.

**Die** — the contract handed to a frontend: `{faces, metadata}`. The rolling UI never touches raw stats, priors, or resampling.

## Pipeline

```
Offline (periodic):
  DataAdapter (population-wide) -> PriorDiscovery -> PriorParams (stored, keyed by stat + scope)

Online (per player, per roll):
  PriorParams + DataAdapter (per-player) -> QualitySampler -> Discretizer -> Die
```

## Explicitly deferred / out of scope for now

- How a per-match "modeled score" (e.g. combining tackles, pass success, halfspace receptions into a role-suitability number) actually gets computed. Assume it already exists as an input value per match.
- A `Combinator` module that combines separately-drawn samples from multiple stats — considered and dropped. If a composite value is ever built by combining raw features, that belongs upstream of the Bayesian layer (as a pre-computed value per match), not as a distribution-combination step downstream of it.

## Data

[data/player_seasons.csv](data/) holds 10,723 Premier League player-seasons from 2006/07 to 2025/26, extracted from the Pulselive API by [empty-head-data](../empty-head-data) (sibling repo, where provider ingestion lives) and described in [research/premier-league-pulselive-api.md](research/premier-league-pulselive-api.md). Its `position_general` column is populated on every row, which makes it the first prior scope; the granular `position` column is blank on 14% of rows.

Season aggregates are the right grain, not a compromise forced by what happens to be pre-computed: a Poisson update depends only on total count and total denominator, so a player's five seasons and the hundred-odd matches inside them produce an identical posterior. Collecting season totals is the cheaper route to the same answer.
