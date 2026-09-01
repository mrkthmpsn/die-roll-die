# die-roll-die

[![test](https://github.com/mrkthmpsn/die-roll-die/actions/workflows/test.yml/badge.svg)](https://github.com/mrkthmpsn/die-roll-die/actions/workflows/test.yml)

die-roll-die is a demonstration of probabilistic statistics (and a Sideshow Bob reference). It takes a set of statistics — for example, a footballer's goals across several seasons — works out a distribution of what the underlying rate might be, then turns that distribution into a weighted die.

A prior is fitted from a population's data (e.g. the goal-scoring rate of forwards in general) and updated with an entity's individual record (e.g. a striker's goals and appearances) to give a posterior over their true rate. To make this easier to conceptualise, the posterior can be turned into a virtual die, to be virtually rolled with results reflecting the probabilities of the data.

The repo includes five seasons of Premier League goals and appearances data taken from Wikipedia, but the underlying framework can be used with your own dataset(s).

## Example
Using the Wikipedia data, here is a die for Erling Haaland's goals over his next 30 appearances, scoped against the prior distribution of forwards in the dataset:

```
$ uv run python examples/roll.py Erling_Haaland --scope position_general=Forward --priors data/priors.json

Erling Haaland (Erling_Haaland) - goals, scope {'position_general': 'Forward'}
  record:    112 in 132.0 appearances across 4 seasons
  prior:     gamma_poisson, 0.197 goals/appearances, worth 11.4 appearances of evidence
  posterior: 0.797 goals/appearances, worth 143.4 appearances of evidence

  a D6 (equal_width) over goals in the next 30 appearances:
      1  12.0-16.2    7.2%
      2  16.2-20.3   19.9%
      3  20.3-24.5   29.2%
      4  24.5-28.7   25.1%
      5  28.7-32.8   13.3%
      6  32.8-37.0    5.3%
```

The `prior` line is what forwards in general score, fitted from the data: 0.197 goals per appearance, carrying as much weight as 11 appearances would. The `posterior` adds Haaland's own 112 goals in 132 appearances, giving 0.797 goals per appearance on 143 appearances of evidence.

Each face of the die covers about four goals and carries its own chance of coming up. A season of 20 to 25 goals (across an imaginary 30 appearances) is the likeliest single outcome at 29%, while 12 to 16 comes up 7% of the time and 33 to 37 comes up 5%. Read down the right-hand column and you are reading the shape of the distribution.

That is a weighted die: goal values on each face evenly split, uneven chances of landing on each face. `--strategy equal_weight` cuts the same numbers the other way — every face equally likely, with the value ranges uneven instead.

## Install

```
uv add die-roll-die
```

or `pip install die-roll-die`. The distribution is `die-roll-die` and the import is
`die_roll_die`:

```python
from die_roll_die import ColumnMap, build_die_from_csv
```

[From a CSV to a die](#from-a-csv-to-a-die) is the shortest working example, and
[Use your own data](#use-your-own-data) covers pointing it at a file of your own.

## Try the demo from a clone

The repository carries the dataset and two example scripts, which an install does not:

```
uv sync
uv run python examples/fit.py
uv run python examples/roll.py Bukayo_Saka --scope position_general=Forward --priors data/priors.json
```

The first command fits a prior for each position group and writes them to `data/priors.json`; the second builds a die for one player. A dataset of 2,804 Premier League player-seasons ships with the repo, so both work on a fresh clone.

Useful flags on `roll.py`: `--faces 20` for a D20, `--denominator 38` to predict over a full 38-appearance season, `--strategy equal_width` for the histogram view.

## What you can point it at

Football is used as an example, but the library is built around the shape of the measurement. There are four shapes it handles, and your data decides which one you have:

**A count over an 'exposure'.** Goals in appearances, tackles in minutes, defects in production hours, support tickets in weeks on the team. You choose how much exposure to predict over — 30 appearances, 900 minutes — and the die is over how many events fall in it.

**A time to an event.** Hours between machine failures, days to close a support ticket, minutes between goals conceded. You choose how many events to predict over — five failures, ten tickets — and the die is over the total time they take. This is the same two quantities as a count over an exposure, with the roles reversed: there you fix the time and count the events, here you fix the events and measure the time.

**Successes out of attempts.** Shots on target out of shots, passes completed out of attempted, free throws made out of taken. You choose how many attempts, and the die is over how many of them come off.

**A measured quantity.** Distance covered per match, revenue per week, hours of downtime per month. You choose how many periods, and the die is over the total across them — so this shape wants quantities that add up to something meaningful.

A composite score — an "inverted full-back suitability out of 10" computed however you like — is consumed rather than modelled here: work out the score per match by whatever formula you please, and feed the scores in as the stat. Note that a score bounded at 0 and 10 is a beta after rescaling to 0-1, not a normal, and that the die will be over the total across the periods you choose rather than the average.

## Use your own data

`CsvDataAdapter` reads any CSV of one row per entity per period. You tell it which columns fill which role:

```python
from die_roll_die import ColumnMap, CsvDataAdapter

columns = ColumnMap(
    entity="player_ref",         # which entity a row belongs to
    entity_type="player",        # what that id names — a literal, not a column
    denominator="attempts",      # what the value was measured against
    name="player",               # a label, for lookups and display
    dimensions=("team", "season"),  # columns you might fit separate priors along
)
adapter = CsvDataAdapter("shooting.csv", columns)
```

Nothing is guessed from a column's name, so a file with its own conventions needs a map rather than a rename. A column you do not map is not lost — it is used one of two other ways:

- **The stat is chosen per question**, not in the map: `get_population_observations("three_pointers")`. One adapter serves every numeric column in the file.
- **A scope may filter on any column**, mapped or not: `{"team": "Harriers"}` works whether or not `team` is a dimension.

Only `scopes_for` is restricted to the mapped dimensions, because it works from `Record`s rather than from the file and a `Record` carries only what the map told it to.

**Choosing the denominator is a modelling decision, not a lookup.** If your file has both `attempts` and `minutes`, then `denominator="attempts"` asks what share of his shots go in, and `denominator="minutes"` asks how many he hits per minute on court. Both are legitimate, they are different questions, and the choice decides which model you want.

## From a CSV to a die

One call does the whole thing:

```python
from die_roll_die import build_die_from_csv

die = build_die_from_csv(
    "shooting.csv", columns,
    stat_id="three_pointers", model="beta_binomial",
    entity_id="player-17", denominator=200,   # the next 200 attempts
)
print(die.model_dump_json(indent=2))
```

It refits the prior from the whole file on every call, so for more than one entity, fit once and reuse:

```python
from die_roll_die import InMemoryPriorStore, create_die, fit_priors

store = InMemoryPriorStore()
report = fit_priors(adapter, store, "three_pointers", "beta_binomial", dimension="position")
prior = store.get("player", "three_pointers", {"position": "Guard"})

for entity_id in squad:
    die = create_die(adapter, prior, entity_id, denominator=200)
```

`fit_priors` returns a `FitReport` naming the scopes it fitted and the ones it skipped, a slice with too few entities being expected when scopes come from a column. `create_die` reads the stat, entity type, scope and model off the prior, so the only thing left to choose is how much opportunity to predict over.

## How it works

**Observations.** Every row becomes a `Record`: an entity, a value, and the denominator that value was measured against. Haaland's four seasons are 36 goals in 35 appearances, 27 in 31, 22 in 31, 27 in 35. The denominator is what separates a rate you can trust from one you cannot.

**A prior** is what you believe about a player before looking at their record — here, what scoring rates Premier League forwards have in general. It is not hand-picked: `fit_prior` reads every forward-season in the file and fits a distribution to the spread of their rates. For goals it comes out as `alpha=2.26, beta=11.44`, which describes a typical forward scoring 0.20 goals per appearance.

**`beta` is evidence measured in appearances**: this prior is worth about 11 appearances of watching someone play, which is what sets how far a player's own record can move it.

**The posterior** is the prior updated with one player's own record, and for this model the update is two additions:

```
alpha:  2.26 + 112 goals       = 114.26
beta:  11.44 + 132 appearances = 143.44
        rate = 114.26 / 143.44 = 0.797 goals per appearance
```

Haaland's raw rate is 112/132 = 0.848, and the posterior says 0.797 — pulled slightly toward the population, because 11 appearances of prior sit against his 132 of evidence. A player with 11 appearances of their own would be pulled halfway instead. That is the whole purpose of the prior: it stops a hot fortnight from reading as greatness, without stopping a long record from speaking for itself.

**Draws.** The posterior is a curve, not a number, so we sample it 100,000 times. Two things vary, and the difference matters:

```
rate draws     10th 0.703   50th 0.794   90th 0.894   ← how sure we are of his rate
count draws    10th 17      50th 24      90th 31      ← what he'd actually score in 30
```

The first is uncertainty about Haaland. The second adds the randomness of football itself: even knowing his rate exactly, thirty appearances is a small sample and goals arrive irregularly. The die is built from the second, which is why it is wider than the first — most of what it shows you is the sport, not your ignorance.

**Faces.** The 100,000 counts are cut into six groups, and there are two ways to do the cutting.

`equal_width`, the default, slices the range of outcomes into six equal spans. **Every face covers the same number of goals and the chances differ** — which is what makes it a weighted die, and why reading down the percentages shows you the distribution's shape.

`equal_weight` sorts the counts and splits them into six piles of the same size instead. **Every face then has the same 1-in-6 chance and the value ranges differ**, narrow where outcomes bunch together and wide out in the tails. That is an unweighted die with uneven faces, and it has one property the other lacks: a physical D6 rolled by hand gives a genuine draw from the posterior, because each face really is equally likely.

## Choosing a model

`fit_prior` makes you name the model, and will not guess. A model is a pair — a prior distribution, and an assumption about what your observations do given it — and it states which values your stat can take **at all**, which no amount of data establishes: a value nobody has recorded and a value nobody can record look identical in a file.

| Model | Rate covers | `value` | `denominator` | Use when |
| --- | --- | --- | --- | --- |
| `gamma_poisson` | positive, no ceiling | count of events | exposure they occurred in | you fixed the time and counted — goals per appearance |
| `gamma_exponential` | positive, no ceiling | amount of time | count of events | you fixed the count and timed it — hours per five incidents |
| `beta_binomial` | 0 to 1, nothing outside | successes | attempts | successes out of attempts — shots on target per shot |
| `normal_normal` | anything, symmetric | measured quantity | weight | measurements away from zero — distance per match |

The two gamma models describe the same quantities, events and time, and differ only in which one your data holds fixed. Their update is identical; what changes is which field holds which, and what `sample_predictive` gives back — a count of events for `gamma_poisson`, a total time for `gamma_exponential`.

Each name joins the prior to the likelihood. "Gamma" and "beta" come from the gamma and beta functions in their formulas rather than from anything about your data, so "beta is the bounded one" is a fact to memorise rather than derive.

### What the parameters are called

Every model's prior and posterior are two numbers, and their names come from the same Greek convention as the model names. `POSTERIOR_PARAM_NAMES` in the library maps each model to the pair it uses, and `DieMetadata.posterior_params` labels its two numbers with it:

| Model | First | Second |
| --- | --- | --- |
| `gamma_poisson` | `alpha`, events counted | `beta`, exposure they occurred in |
| `gamma_exponential` | `alpha`, events counted | `beta`, the time they took |
| `beta_binomial` | `alpha`, successes | `beta`, failures |
| `normal_normal` | `mu`, the estimated mean | `sigma`, how uncertain that mean is |

Three of the four call their pair `alpha` and `beta`, so **`beta` is a parameter of three models and the name of one**, and a `gamma_poisson` prior has a parameter called `beta` while having nothing to do with the beta distribution. The gamma arithmetic worked through [above](#how-it-works) is what the first two rows look like in practice: goals added to `alpha`, appearances added to `beta`, and `alpha / beta` the rate that comes out. For `beta_binomial` the equivalent is `alpha / (alpha + beta)`, the share of attempts that succeeded.

A `normal_normal` prior carries a third number, `sigma_obs`, which is how much individual observations vary rather than how uncertain the mean is — the two `sigma`s answer different questions, and the Design notes below cover where the third comes from.

**Getting it wrong does not fail loudly.** Fit a 90% free-throw shooter as `gamma_poisson` instead of `beta_binomial` and everything runs — but a gamma has no ceiling, so 21% of the resulting die describes making more than 100 shots out of 100 attempts, and nothing in the output says so. Two guards exist: the beta fit rejects any row whose value exceeds its own denominator, and the gamma-exponential fit rejects a value or denominator that is not positive.

## Modules

**DataAdapter** — the only domain-aware module. Supplies one entity's observations, and the population's, as `Record`s. `CsvDataAdapter` implements it over a CSV; anything else — a database, an HTTP API — implements the same two methods.

**PriorDiscovery** — `fit_prior` fits a model's parameters from population-wide observations by method of moments. `scopes_for` and `fit_scopes` run it across a list of scopes, saving what fits and reporting the slices too thin to fit.

**PriorStore** — persists fitted priors, keyed by `(entity_type, stat_id, scope)`. `InMemoryPriorStore` for a process, `JsonPriorStore` for a file. That file carries a `schema_version` of its own, and one stating a version the library does not read raises rather than being read as the current shape; the key is rebuilt from each prior on load rather than written down, so changing how it is built cannot strand entries behind a lookup that misses. Fitting is an offline job; rolling a die reads what it wrote.

**QualitySampler** — `sample(entity_id, n_draws)` returning draws of an entity's underlying quality. `PosteriorSampler` does the conjugate update and also offers `sample_predictive(entity_id, n_draws, denominator)`, which is what a die is built from. That denominator has to be positive: over zero opportunity every draw is the same number, which is one outcome rather than the spread a die represents. Its `posterior_params` returns the two numbers as a bare tuple, which `POSTERIOR_PARAM_NAMES` gives the names of. `BootstrapSampler` draws without a prior, resampling the entity's own records with replacement and taking summed values over summed denominators each time.

**Errors** — two trees, both under `ValueError` so a caller catching that keeps working. `PriorFitError` covers fitting, with `InsufficientData` for a scope holding too little to estimate from and `UnsuitableModel` for observations that contradict the model asked for. `SamplingError` covers drawing, with `EntityTypeMismatch`, `MissingPriorParam`, `UnsuitableDenominator` and `InsufficientObservations`. Neither tree is under the other, so a handler around `create_die` can tell a prior that would not fit from a die that cannot be rolled.

**Pipeline** — `fit_priors` fits the global scope plus one per value of a dimension and saves them to a store; `create_die` turns an entity and a prior into a `Die` with its metadata filled in; `build_die_from_csv` runs both against a CSV in one call, refitting the prior each time.

**Discretizer** — `discretize(samples, n_faces, strategy)` turns a sample array into weighted faces. `equal_weight` holds the probabilities equal and lets the value ranges vary; `equal_width` holds the value ranges equal and lets the probabilities vary. It knows nothing about what the numbers mean.

**Die** — `{schema_version, faces, metadata}`, serialising with `model_dump_json()`. The version is the payload's first key, so a consumer can branch on it before parsing the rest; it rises when a field is renamed, removed or changes meaning, and stays put when an optional field is added. `assemble_die_from_samples` is the last step, cutting a list of samples into faces; `DieMetadata` is typed rather than a free dict, so a consumer can rely on the names: entity, stat, scope, the prior behind it, the posterior's parameters, the record it was built from and how many observations that spans, and what denominator it predicts over. The posterior's two parameters are keyed by `POSTERIOR_PARAM_NAMES` under the prior's model, and `PriorParams.ordered_params` reads a prior's own pair out in the same order.

```
Offline (periodic):  DataAdapter (population) -> fit_prior -> PriorStore          [fit_priors]
Online (per roll):   PriorStore + DataAdapter (one entity) -> QualitySampler
                       -> Discretizer -> Die                                     [create_die]
```

## Design notes

**The prior fit corrects for noise in its own inputs.** A season's goals-per-appearance is spread by two things: how much players genuinely differ, and the randomness of scoring itself. Only the first belongs in a prior. For counts the second is calculable — a Poisson's spread is fixed by its mean — so it is subtracted. Over the 483 forward-seasons of ten or more appearances in the shipped data, 34% of the apparent spread is that randomness, and correcting for it takes the prior from 7.5 to 11.4 appearances' worth of evidence. Seasons under ten appearances are excluded outright, their rates being dominated by the small denominator — and the threshold is a modelling choice, since a prior over any forward would include everybody while a prior over a forward who plays should not.

`normal_normal` cannot do this, because a normal's spread is not implied by its mean. `fit_prior` instead estimates it by pooling how much each entity's observations vary around that entity's own mean, which needs entities appearing more than once and is stored as the prior's third parameter, `sigma_obs`.

**A missing scope fails rather than falling back.** Ask for a prior nobody fitted and you get an error listing what exists, not the next broadest prior. A die built from the forwards prior and one built from the global prior are different answers, and nothing downstream could tell them apart. `list_scopes` lets a caller see what is available so the choice stays theirs.

**Draws outside the 1st and 99th percentiles are dropped before binning.** Without that, an outer face reports the single most extreme draw as its bound — and that bound moves with how many draws you asked for, climbing from 46 to 73 as the count went from a thousand to half a million. Clipping is skipped when there are too few samples for the tails to hold one, so it applies from about a hundred upward. Pass `clip=None` to keep everything.

**Adjacent equal-mass faces can share an integer bound.** A D20 over predicted goals showed faces of `21`, `21-22` and `22`, so 22 goals is an outcome on three faces of twenty. That is the die being honest about a count distribution having fewer distinct values than the die has faces; the weights stay correct.

**`BootstrapSampler` resamples whole records, so what a record is becomes a modelling choice.** It draws rows rather than numbers, keeping each value with the denominator it was measured against — case resampling, which is the standard treatment for a ratio and the only one under which a draw means anything, since resampling values and denominators separately would pair a season's goals with another season's appearances. `PosteriorSampler` by contrast only ever sums values and denominators, so a player's goals and nineties total the same whether they arrive as four seasons or 150 matches and the posterior die is identical either way — the Gamma-Poisson already treats a season as a bag of independent minutes. Resampling reuses whole rows, so it gives a different answer at each granularity, and a match is the unit it wants: three to six season rows are too few for the spread of the resampled rates to mean much.

**The ratio of sums is biased when the denominators differ**, which is the known cost of case resampling rather than something granularity-independent. Averaging the draws counts every resample once however much exposure it drew, while the resamples that happen to omit a long record are also the high-rate ones, so the draws centre above the pooled rate — by 7% over three seasons of 10 goals in 20 nineties, 20 in 30 and 6 in 50. It falls away roughly as one over the record count, reaching under a thousandth by 150 rows, which is another reason the match is the unit. `data/player_seasons.csv` is season totals, so the shipped data demonstrates the posterior rather than the bootstrap.

**Entity type is in the store key** so goals-per-player and goals-per-club can share a store, and `PosteriorSampler` raises rather than shrinking a player toward a club's prior.

## Data

[data/player_seasons.csv](data/player_seasons.csv) holds 2,804 player-seasons of Premier League goals and appearances covering 2021/22 to 2025/26. [tools/wikipedia_squads.py](tools/wikipedia_squads.py) built it from the squad statistics tables of Wikipedia's club-season articles and can rebuild it; [data/README.md](data/README.md) describes the columns and their caveats.

The denominator is appearances rather than minutes, because Wikipedia records minutes on almost no club-season article. A five-minute substitute appearance therefore counts as much as ninety, which widens the fitted priors relative to a per-90 denominator.

## Licence

The software — `die_roll_die/`, `examples/`, `tools/` and `tests/` — is MIT, in [LICENSE](LICENSE).

`data/` is not: it derives from Wikipedia, whose text is CC BY-SA 4.0, so the dataset carries the same licence and its own attribution in [data/LICENSE](data/LICENSE). The two are separate works in one tree, which is why a fork may take the library closed-source while the data file keeps its terms. Redistributing the data, modified or not, means keeping that licence and the notices with it.

## Development

```
uv sync
uv run pytest
```

Every push runs the suite on Python 3.11, 3.12 and 3.13 on Linux, installing with
`uv sync --frozen` so that a lock which has drifted from `pyproject.toml` fails the run, then
fits priors and rolls a die through the two example scripts. A second job builds the wheel
and checks the typing marker is inside it.

The package ships a PEP 561 `py.typed` marker, so an install carries its annotations and
`Die`, `PriorParams` and the rest keep their field types under mypy or pyright rather than
resolving to `Any`.

`die_roll_die.__version__` reports the version, so a bug report can name one. It is the
single source: `pyproject.toml` declares the version dynamic and `[tool.hatch.version]`
reads it out of `die_roll_die/__init__.py` at build time.
