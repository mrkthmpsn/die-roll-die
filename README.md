# die-roll-die

[![test](https://github.com/mrkthmpsn/die-roll-die/actions/workflows/test.yml/badge.svg)](https://github.com/mrkthmpsn/die-roll-die/actions/workflows/test.yml)

die-roll-die is a demonstration of probabilistic statistics (and a Sideshow Bob reference). It takes a set of statistics — for example, a footballer's goals across several seasons — works out a distribution of what the underlying rate might be, then turns that distribution into a weighted die (like [here](https://lucky-scout.vercel.app)).

A prior is fitted from a population's data (e.g. the goal-scoring rate of forwards in general) and updated with an entity's individual record (e.g. a striker's goals and appearances) to give a posterior over their true rate. To make this easier to conceptualise, the posterior can be turned into a virtual die, to be virtually rolled with results reflecting the probabilities of the data.

The repo includes five seasons of Premier League goals and appearances data taken from Wikipedia, but the underlying framework can be used with your own dataset(s).

## Example
Using the Wikipedia data, here is a die for Erling Haaland's goals over his next 30 appearances, scoped against the prior distribution of forwards in the dataset. `data/priors.json` is generated rather than committed, so `uv run python examples/fit.py` writes it before this runs:

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

The `prior` line is what forwards in general score, fitted from the data: 0.197 goals per appearance. A prior's strength is measured in the same units as the denominator, so this one counts for about as much as watching a player for 11 appearances — and a player's own record outweighs it from there. The `posterior` adds Haaland's own 112 goals in 132 appearances, giving 0.797 goals per appearance on 143 appearances of evidence.

In this example, each face of the die covers about four goals but is weighted with its own chance of coming up. A season of 20 to 25 goals (across an imaginary 30 appearances) is the likeliest single outcome at 29%, while 12 to 16 comes up 7% of the time and 33 to 37 comes up 5%. Read down the right-hand column and you are reading the shape of the distribution.

That is the default strategy, a weighted die approach: goal values on each face evenly split, uneven chances of landing on each face. `--strategy equal_weight` cuts the same numbers the _other_ way: every face on the die becomes equally likely, but with the value ranges uneven instead.

## Install

```
uv add git+https://github.com/mrkthmpsn/die-roll-die
```

or `pip install git+https://github.com/mrkthmpsn/die-roll-die`. The library is not on PyPI, so
the install comes from the repository; the distribution is `die-roll-die` and the import is
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

Useful flags on `roll.py`: `--faces 20` for a D20 (for all you D&D fans), `--denominator 38` to predict over a full 38-appearance season, `--strategy equal_weight` for six equally likely faces instead.

## What you can point it at

Football is used as an example, but the library is built around data rather than anything sport-specific. There are four shapes the library handles:

**A count over an 'exposure' (`gamma_poisson`).** E.g. goals in appearances, tackles in minutes, defects in production hours, support tickets in weeks on the team. You choose how much exposure to predict over — 30 appearances, 900 minutes — and the die faces are therefore how many events fall in that exposure time.

**A time to an event (`gamma_exponential`).** E.g. hours between machine failures, days to close a support ticket, minutes between goals conceded. You choose how many events to predict over — five failures, ten tickets — and values of the die faces are the total time they take. This is the role reversal of the above, a count over an exposure: there you fix the time and count the events, here you fix the events and measure the time.

**Successes out of attempts (`beta_binomial`).** E.g. shots on target out of shots, passes completed out of attempted, free throws made out of taken. You choose how many attempts, and the die face values relate to how many of them come off.

**A measured continuous quantity (`normal_normal`).** E.g. distance covered per match, revenue per week, hours of downtime per month. You choose how many periods, and the die face values are based on the total across them — so this shape wants quantities that add up to something meaningful.

## Use your own data

`CsvDataAdapter` reads any CSV file arranged as one row per entity per period. You tell it which columns fill four fixed roles using the `ColumnMap` schema:

```python
from die_roll_die import ColumnMap, CsvDataAdapter

columns = ColumnMap(
    entity="player_ref",         # which entity a row belongs to
    entity_type="player",        # [*not* a column] what that id names — an actual string literal
    denominator="attempts",      # what the value was measured against
    name="player",               # a label, for lookups and display
    dimensions=("team", "position"),  # columns you might fit separate priors along
)
adapter = CsvDataAdapter("shooting.csv", columns)
```

There's no auto-determination of column type based on its name or contents, so a file with its own conventions needs a map. A column you do not map is not necessarily lost though; it can be used one of two other ways:

- **Chosen as the stat in a call**: e.g. `get_population_observations("three_pointers")`. Any column holding numbers can be the stat, so one adapter answers every numeric question the file supports.
- **Named in a scope**: e.g. `{"game_type": "playoff"}` filters on a column the map never mentions. A scope is a set of column-value pairs narrowing which rows a prior is fitted from, and the same filter later picks which of an entity's own rows update it. Scope keys are checked against the file's header rather than the map, and matched as exact text against the cell.

**Choosing the denominator is a modelling decision, not a lookup.** If your file has both `attempts` and `minutes`, then `denominator="attempts"` asks what share of his shots go in, and `denominator="minutes"` asks how many he hits per minute on court. Both are legitimate, they are different questions, and the choice decides which model you want.

## From a CSV to a die

If you want one function to do the end-to-end process...

```python
from die_roll_die import build_die_from_csv

die = build_die_from_csv(
    "shooting.csv", columns,
    stat_id="three_pointers", model="beta_binomial",
    entity_id="player-17", denominator=200,   # the next 200 attempts
)
print(die.model_dump_json(indent=2))
```

The function refits the prior from the whole file on every call, so for more than one entity it's recommended to fit once and reuse, as below:

```python
from die_roll_die import CsvDataAdapter, InMemoryPriorStore, create_die, fit_priors

adapter = CsvDataAdapter("shooting.csv", columns)   # `columns` from "Use your own data"
store = InMemoryPriorStore()
report = fit_priors(adapter, store, "three_pointers", "beta_binomial", dimension="position")
prior = store.get("player", "three_pointers", {"position": "Guard"})

for entity_id in ["player-17", "player-22", "player-38"]:
    die = create_die(adapter, prior, entity_id, denominator=200)
```

`fit_priors` returns a `FitReport` naming the scopes it fitted and the ones it skipped (e.g. all values are zero, like creating priors for player position but all goalkeepers have a 0 value for goals scored). `create_die` reads the stat, entity type, scope and model off the prior, so the only thing left to choose is how much opportunity to predict over.

## Choosing a model

`fit_prior` makes you name the model that should be used. The accepted values are a pair of a prior distribution and an assumption about what your observations do given it (allowing two versions of gamma distribution).

The four shapes in [What you can point it at](#what-you-can-point-it-at) are these four models:

| Model | Rate covers | `value` | `denominator` |
| --- | --- | --- | --- |
| `gamma_poisson` | positive, no ceiling | count of events | exposure they occurred in |
| `gamma_exponential` | positive, no ceiling | amount of time | count of events |
| `beta_binomial` | 0 to 1, nothing outside | successes | attempts |
| `normal_normal` | anything, symmetric | measured quantity | weight |

The two gamma models describe the same quantities, events and time, and differ only in which one your data holds fixed. Both add your events to `alpha` and your time to `beta`; what changes is which field holds which, and what the library draws from the finished posterior — a count of events for `gamma_poisson`, a total time for `gamma_exponential`.

Each name joins the prior distribution to that assumption about the observations, which is called the likelihood. "Gamma" and "beta" come from the gamma and beta functions in their formulas rather than from anything about your data, so "beta is the bounded one" is a fact to memorise rather than derive.

### What the parameters are called

Every model's prior, and the posterior it becomes once an entity's record is added, are two numbers, and their names come from the same Greek convention as the model names. `POSTERIOR_PARAM_NAMES` in the library maps each model to the pair it uses, and `DieMetadata.posterior_params` labels its two numbers with it:

| Model | First | Second |
| --- | --- | --- |
| `gamma_poisson` | `alpha`, events counted | `beta`, exposure they occurred in |
| `gamma_exponential` | `alpha`, events counted | `beta`, the time they took |
| `beta_binomial` | `alpha`, successes | `beta`, failures |
| `normal_normal` | `mu`, the estimated mean | `sigma`, how uncertain that mean is |

Three of the four call their pair `alpha` and `beta`, so **`beta` is a parameter of three models and the name of one**, and a `gamma_poisson` prior has a parameter called `beta` while having nothing to do with the beta distribution. For the two gamma models that is goals added to `alpha`, appearances added to `beta`, and `alpha / beta` the rate that comes out. For `beta_binomial` the equivalent is `alpha / (alpha + beta)`, the share of attempts that succeeded.

A `normal_normal` prior carries a third number, `sigma_obs`, which is how much individual observations vary rather than how uncertain the mean is — the two `sigma`s answer different questions. `fit_prior` estimates the third by pooling how much each entity's observations vary around that entity's own mean, so it needs entities appearing more than once.

**Getting it wrong does not fail loudly.** Fit a 90% free-throw shooter as `gamma_poisson` instead of `beta_binomial` and everything runs — but a gamma has no ceiling, so 21% of the resulting die describes making more than 100 shots out of 100 attempts, and nothing in the output says so. Three guards exist: the beta fit rejects any row whose value is negative or exceeds its own denominator, and rejects proportions more spread than any beta with their mean; the gamma-exponential fit rejects a value or denominator that is not positive.

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

See [CONTRIBUTING.md](CONTRIBUTING.md)
