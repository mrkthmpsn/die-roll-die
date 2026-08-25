# die-scouting

Turn a Bayesian estimate of "quality" (a stat, or a pre-computed score for a specific role) into a weighted die, and roll it — a small illustrative tool for visualizing uncertainty in player-quality estimates.

## Status

The pipeline runs end to end on the dataset in [data/](data/), which ships with the repo: `CsvDataAdapter` reads it, `PriorDiscovery` fits a prior from it, and `PosteriorSampler` updates that prior for one player and feeds `Discretizer`. [examples/roll.py](examples/roll.py) does all of it for a named player and any stat.

All three prior families are implemented in `fit_prior` and `PosteriorSampler`, and priors can be fitted once and stored. `BootstrapSampler` still raises `NotImplementedError`.

```
uv run python examples/roll.py "Erling Haaland" --scope position_general=Forward
```

## Development

```
uv sync
uv run pytest
```

## Core idea

Any value for a player (a raw stat like goals, or an externally-modeled score like "inverted full-back suitability out of 10") is treated as a stream of observations, each pairing a value with the denominator it accumulated over — twelve goals across thirty nineties, say. Bayesian updating turns "prior belief + this player's own record" into a posterior distribution over their true quality. That posterior gets discretized into weighted die faces and rolled.

The denominator is what makes the die worth looking at: four goals in ten appearances and forty in a hundred imply the same rate, and only the second is evidence you can lean on. Two questions can be asked of the posterior — what the player's underlying rate is, and how many they would record over a stated amount of future playing time.

## Modules

**DataAdapter** — the only provider/domain-aware module. Supplies per-observation values for one player, and population-wide values across many players (for prior discovery). Everything else is domain-agnostic.

`CsvDataAdapter` implements it over a player-season CSV, reading any numeric column as the stat and any column as a scope filter, so the same class serves both the goals example and a future modelled score.

**PriorDiscovery** (offline, periodic) — empirical Bayes: fits a prior distribution's parameters from the population-wide spread of a stat, rather than requiring someone to hand-pick numbers. The distribution family is supplied by the caller rather than chosen from the stat's name — Beta for proportions bounded by 0 and 1, Gamma for positive quantities with no ceiling, Normal for values that can sit anywhere. The family states which values the stat can take at all, and no sample establishes that, because an unobserved value and an impossible one look identical in data; the parameters are then fitted from the population by method of moments. All three are implemented.

Each family corrects for the noise in its own inputs, and where that noise comes from differs. A Poisson's spread is fixed by its mean and a binomial's by its mean and its attempts, so both can be calculated and subtracted; a normal's is free, so `fit_prior` estimates it by pooling how much each entity's observations vary around that entity's own mean, which needs entities appearing more than once and is stored as the prior's third parameter, `sigma_obs`.

The gamma fit corrects for the noise in its own inputs. A season's goals-per-appearance is spread both by how much players genuinely differ and by the randomness of scoring itself, the second contributing `mean / denominator` to the variance of an observed rate; subtracting its average leaves the spread a prior should carry. Over the 524 forward-seasons of five or more appearances in the shipped data, 38% of the apparent spread is that randomness, and correcting for it takes the prior from 7.0 to 11.2 appearances' worth of evidence — the difference between a player with three goals in four appearances reading as a genuine 0.75-per-appearance striker or not. Seasons under five appearances are excluded from the fit outright, their rates being dominated by the small denominator.

Scope is optional and composable — a prior can be global, or narrowed by any combination of dimensions (e.g. position group, competition). Stored as `PriorParams` keyed by `(stat_id, scope)`, in an `InMemoryPriorStore` or a `JsonPriorStore`.

Which scopes exist is a list someone writes down rather than something the system derives. `scopes_for` builds that list from the distinct values of a column, and `fit_scopes` fits each one, saving what fits and reporting the slices too thin to fit. A scope nobody fitted is a miss at read time, not a silent fall back to a broader prior, because a die built from the forwards prior and one built from the global prior are different answers and nothing downstream could tell them apart. `list_scopes` tells a caller what is available so the choice stays theirs:

```
data/priors.json holds no prior for 'goals' scoped to {'position_general': 'Forward', 'season_name': '2024/25'}
scopes fitted for 'goals':
  {'position_general': 'Defender'}
  {'position_general': 'Forward'}
  {'position_general': 'Goalkeeper'}
  {'position_general': 'Midfielder'}
  global
```

**QualitySampler** (online, per player/roll) — uniform interface: `sample(entity_id, n_draws) -> float[]`, returning draws of the player's underlying rate. Two implementations behind it:

- `PosteriorSampler` — closed-form posterior (conjugate update of the discovered prior with this player's own observations). Gamma updates as Gamma-Poisson, summing values and denominators onto `alpha` and `beta`; beta updates as Beta-Binomial, summing successes onto `alpha` and misses onto `beta`; normal updates by precision-weighting the prior's mean against the observations. It also offers `sample_predictive(entity_id, n_draws, denominator)`, which draws the player's underlying quality and then what they would record over the given denominator — a Poisson count for gamma, binomial successes for beta, a summed value for normal — so the die is over goals-next-season rather than goals-per-ninety. That denominator is supplied by the caller and held fixed, so the answer is "if they play thirty nineties" rather than "next season" — playing time is not itself modelled.
- `BootstrapSampler` — resample this player's own match records with replacement, recompute, repeat — no named distribution family required

Reads the relevant `PriorParams` as config; never invokes `PriorDiscovery` itself.

**Discretizer** — pure stats, no domain knowledge: bins a sample array into weighted die faces (`{label, weight, value_range}`), by equal-mass or equal-width bin strategy. The face count is caller-chosen, so the same sample array can produce a D6, a D20, or any other die.

Implemented. `equal_mass` splits sorted samples into evenly-sized chunks, so every face carries roughly equal probability and the faces differ in how wide a value range they cover. `equal_width` splits the observed range into fixed-width bins, so the faces differ in weight instead.

On whole-number samples, adjacent `equal_mass` faces can report the same integer as their bounds — a D20 over predicted goals showed faces of `21`, `21-22` and `22`, so 22 goals is an outcome on three faces of twenty. That is the die being honest about a count distribution having fewer distinct values than it has faces, and the weights stay correct.

Samples outside the 1st and 99th percentiles are dropped before binning, by default. Without that, an outer face reports the single most extreme draw as its bound — a die over predicted goals showed a top face of `14-73` where that outcome had probability 2e-6, and the bound climbed from 46 to 73 as the draw count went from a thousand to half a million. Clipping is skipped where the sample count is too small for the tails to hold a whole sample, so the default applies from a hundred samples upward. Pass `clip=None` to bin every sample.

**Die** — the contract handed to a frontend: `{faces, metadata}`, serialising with `model_dump_json()`. The rolling UI never touches raw stats, priors, or resampling.

`metadata` is a `DieMetadata` rather than a free dict, so a consumer can rely on the names: which entity and stat, the scope, the whole `PriorParams` behind it, the posterior's parameters, the entity's own record, what denominator the die predicts over and in what units. `build_die` stamps the binning strategy and the draw count itself. Two dice for the same player under different scopes are different answers, and this is what lets anything holding them tell which is which.

## Pipeline

```
Offline (periodic):
  DataAdapter (population-wide) -> PriorDiscovery -> PriorParams (stored, keyed by stat + scope)

Online (per player, per roll):
  PriorParams + DataAdapter (per-player) -> QualitySampler -> Discretizer -> Die
```

Each half is a script:

```
uv run python examples/fit_priors.py
uv run python examples/roll.py "Erling Haaland" --scope position_general=Forward --priors data/priors.json
```

Without `--priors`, `roll.py` fits the prior inline and discards it, which is fine for one die and wrong for anything answering requests.

## Data

[data/player_seasons.csv](data/player_seasons.csv) ships with the repo: 2,753 player-seasons of Premier League goals and appearances covering 2021/22 to 2025/26, so a fresh clone can roll a die without finding data first. [tools/wikipedia_squads.py](tools/wikipedia_squads.py) built it from the squad statistics tables of Wikipedia's club-season articles and can rebuild it; [data/README.md](data/README.md) describes the columns and what was dropped.

Exposure is appearances rather than minutes, because Wikipedia records minutes on almost no club-season article. A five-minute substitute appearance therefore counts as much as ninety, which widens the fitted priors relative to a per-90 denominator.

`CsvDataAdapter` reads any CSV of one row per entity per period, given the column names to treat as the entity, the denominator and the label; football player-seasons are what it was built against, but nothing in `die_scouting/` knows that.

## Licence

The software — `die_scouting/`, `examples/`, `tools/` and `tests/` — is MIT, in [LICENSE](LICENSE).

`data/` is not: it derives from Wikipedia, whose text is CC BY-SA 4.0, so the dataset carries the same licence and its own attribution in [data/LICENSE](data/LICENSE). The two are separate works in one tree, which is why a fork may take the library closed-source while the data file keeps its terms. Redistributing the data, modified or not, means keeping that licence and the notices with it.
