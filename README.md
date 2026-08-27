# die-scouting

die-scouting is a demonstration of probabilistic statistics. It takes a set of statistics — for example, a footballer's goals across several seasons — works out a distribution of what that player's underlying scoring rate might be, and turns that distribution into a weighted die.

The distribution is the substance. A prior is fitted from the population — what forwards in general score — and updated with the player's own record to give a posterior over their true rate. How far that posterior sits from their raw rate depends on how much evidence they bring: four good games barely move it off the population, four good seasons move it almost all the way. That pull is shrinkage, and it is most of what the die is showing you.

The die is how you see it. A distribution is hard to read as a curve or a pair of parameters, and easy to read as six faces with percentages against them — and once it is a die, you can roll it, and one roll hands you a plausible season.

Premier League data ships with the repo, but the statistics underneath are general: counts over an exposure, successes out of attempts, or a measurement repeated over time. What is here is a small set of statistical building blocks, demonstrated on football because football has convenient data.

Here is a die for Erling Haaland's goals over his next 30 appearances:

```
$ uv run python examples/roll.py Erling_Haaland --scope position_general=Forward --priors data/priors.json

Erling Haaland (Erling_Haaland) - goals, scope {'position_general': 'Forward'}
  record:    112 in 132.0 appearances across 4 seasons
  prior:     gamma, 0.184 per unit (worth 11.1 of denominator)
  posterior: 0.797 per unit (worth 143.1 of denominator)

  a D6 (equal_width) over goals in the next 30 appearances:
      1  12.0-16.2    7.2%
      2  16.2-20.3   19.6%
      3  20.3-24.5   29.5%
      4  24.5-28.7   25.2%
      5  28.7-32.8   13.3%
      6  32.8-37.0    5.2%
```

Each face covers about four goals and carries its own chance of coming up. A season of 20 to 25 goals is the likeliest single outcome at 29%, while 12 to 16 comes up 7% of the time and 33 to 37 comes up 5%. Read down the right-hand column and you are reading the shape of the distribution.

That is a weighted die: even faces, uneven chances. `--strategy equal_weight` cuts the same numbers the other way — every face equally likely, with the value ranges uneven instead — which is an unweighted die you could fairly roll by hand, and a less direct read.

## Try it

```
uv sync
uv run python examples/fit_priors.py
uv run python examples/roll.py Bukayo_Saka --scope position_general=Forward --priors data/priors.json
```

The first command fits a prior for each position group and writes them to `data/priors.json`; the second builds a die for one player. A dataset of 2,804 Premier League player-seasons ships with the repo, so both work on a fresh clone.

Useful flags on `roll.py`: `--faces 20` for a D20, `--denominator 38` to predict over a full season, `--strategy equal_width` for the histogram view, and `--json` to see the payload a frontend would receive.

## What you can point it at

The library is built around the shape of the measurement, not the sport. There are three shapes it handles, and your data decides which one you have:

**A count over an exposure.** Goals in appearances, tackles in minutes, defects in production hours, support tickets in weeks on the team. The die is over "how many, next time".

**Successes out of attempts.** Shots on target out of shots, passes completed out of attempted, free throws made out of taken. The die is over "how many of the next hundred".

**A measured quantity.** Distance covered per match, average pass length, or a modelled score — an "inverted full-back suitability out of 10" computed however you like, which arrives here as one number per match and gets the same treatment as goals.

The last one is worth dwelling on: this library does not model composite scores, it consumes them. If you have a formula that scores players out of 10, feed the scores in and roll the result.

## Use your own data

`CsvDataAdapter` reads any CSV of one row per entity per period. You tell it which columns fill which role:

```python
from die_scouting import ColumnMap, CsvDataAdapter

adapter = CsvDataAdapter("shooting.csv", ColumnMap(
    entity="player_ref",         # which entity a row belongs to
    entity_type="player",        # what that id names — a literal, not a column
    denominator="attempts",      # what the value was measured against
    name="player",               # a label, for lookups and display
    dimensions=("team", "season"),  # columns you might fit separate priors along
))
```

Nothing is guessed from a column's name, so a file with its own conventions needs a map rather than a rename. A column you do not map is not lost — it is used one of two other ways:

- **The stat is chosen per question**, not in the map: `get_population_observations("three_pointers")`. One adapter serves every numeric column in the file.
- **A scope may filter on any column**, mapped or not: `{"team": "Harriers"}` works whether or not `team` is a dimension.

Only `scopes_for` is restricted to the mapped dimensions, because it works from `Record`s rather than from the file and a `Record` carries only what the map told it to.

**Choosing the denominator is a modelling decision, not a lookup.** If your file has both `attempts` and `minutes`, then `denominator="attempts"` asks what share of his shots go in, and `denominator="minutes"` asks how many he hits per minute on court. Both are legitimate, they are different questions, and the choice decides which distribution family you want.

## How it works

**Observations.** Every row becomes a `Record`: an entity, a value, and the denominator that value was measured against. Haaland's four seasons are 36 goals in 35 appearances, 27 in 31, 22 in 31, 27 in 35. The denominator is what separates a rate you can trust from one you cannot.

**A prior** is what you believe about a player before looking at their record — here, what scoring rates Premier League forwards have in general. It is not hand-picked: `fit_prior` reads every forward-season in the file and fits a distribution to the spread of their rates. For goals it comes out as `alpha=2.04, beta=11.09`, which describes a typical forward scoring 0.18 goals per appearance.

That second number is the useful one. **`beta` is evidence measured in appearances** — this prior is worth about 11 appearances of watching someone play. That is what makes the next step behave sensibly.

**The posterior** is the prior updated with one player's own record, and for this family the update is two additions:

```
alpha:  2.04 + 112 goals       = 114.04
beta:  11.09 + 132 appearances = 143.10
        rate = 114.04 / 143.10 = 0.797 goals per appearance
```

Haaland's raw rate is 112/132 = 0.848, and the posterior says 0.797 — pulled slightly toward the population, because 11 appearances of prior sit against his 132 of evidence. A player with only 12 appearances would be pulled most of the way instead. That is the whole purpose of the prior: it stops a hot fortnight from reading as greatness, without stopping a long record from speaking for itself.

**Draws.** The posterior is a curve, not a number, so we sample it 100,000 times. Two things vary, and the difference matters:

```
rate draws     10th 0.703   50th 0.795   90th 0.894   ← how sure we are of his rate
count draws    10th 17      50th 24      90th 31      ← what he'd actually score in 30
```

The first is uncertainty about Haaland. The second adds the randomness of football itself: even knowing his rate exactly, thirty appearances is a small sample and goals arrive irregularly. The die is built from the second, which is why it is wider than the first — most of what it shows you is the sport, not your ignorance.

**Faces.** The 100,000 counts are cut into six groups, and there are two ways to do the cutting.

`equal_width`, the default, slices the range of outcomes into six equal spans. **Every face covers the same number of goals and the chances differ** — which is what makes it a weighted die, and why reading down the percentages shows you the distribution's shape.

`equal_weight` sorts the counts and splits them into six piles of the same size instead. **Every face then has the same 1-in-6 chance and the value ranges differ**, narrow where outcomes bunch together and wide out in the tails. That is an unweighted die with uneven faces, and it has one property the other lacks: a physical D6 rolled by hand gives a genuine draw from the posterior, because each face really is equally likely.

## Choosing a family

`fit_prior` makes you name the distribution family, and will not guess. The family states which values your stat can take **at all**, and no amount of data establishes that — a value nobody has recorded and a value nobody can record look identical in a file.

| Family | Allows | Use when |
| --- | --- | --- |
| `gamma` | any positive number, no ceiling | counts over an exposure — goals per appearance |
| `beta` | 0 to 1 and nothing outside | successes out of attempts — shots on target per shot |
| `normal` | anything, symmetric around a middle | measurements comfortably away from zero — distance per match |

The names carry no meaning about your data. They come from the gamma and beta functions that appear in the formulas, so "beta is the bounded one" is a fact to memorise rather than derive.

**Getting it wrong does not fail loudly.** Fit a 90% free-throw shooter as a gamma instead of a beta and everything runs — but a gamma has no ceiling, so 21% of the resulting die describes making more than 100 shots out of 100 attempts, and nothing in the output says so. The one guard that exists is in the beta fit, which rejects any row whose value exceeds its own denominator, because that is not successes-out-of-attempts however you squint at it.

## Modules

**DataAdapter** — the only domain-aware module. Supplies one entity's observations, and the population's, as `Record`s. `CsvDataAdapter` implements it over a CSV; anything else — a database, an HTTP API — implements the same two methods.

**PriorDiscovery** — `fit_prior` fits a family's parameters from population-wide observations by method of moments. `scopes_for` and `fit_scopes` run it across a list of scopes, saving what fits and reporting the slices too thin to fit.

**PriorStore** — persists fitted priors, keyed by `(entity_type, stat_id, scope)`. `InMemoryPriorStore` for a process, `JsonPriorStore` for a file. Fitting is an offline job; rolling a die reads what it wrote.

**QualitySampler** — `sample(entity_id, n_draws)` returning draws of an entity's underlying quality. `PosteriorSampler` does the conjugate update and also offers `sample_predictive(entity_id, n_draws, denominator)`, which is what a die is built from. `BootstrapSampler` is not implemented.

**Discretizer** — `discretize(samples, n_faces, strategy)` turns a sample array into weighted faces. `equal_weight` holds the probabilities equal and lets the value ranges vary; `equal_width` holds the value ranges equal and lets the probabilities vary. It knows nothing about what the numbers mean.

**Die** — `{faces, metadata}`, serialising with `model_dump_json()`. `DieMetadata` is typed rather than a free dict, so a consumer can rely on the names: entity, stat, scope, the prior behind it, the posterior's parameters, the record it was built from, and what denominator it predicts over.

```
Offline (periodic):  DataAdapter (population) -> fit_prior -> PriorStore
Online (per roll):   PriorStore + DataAdapter (one entity) -> QualitySampler -> Discretizer -> Die
```

## Design notes

**The prior fit corrects for noise in its own inputs.** A season's goals-per-appearance is spread by two things: how much players genuinely differ, and the randomness of scoring itself. Only the first belongs in a prior. For counts the second is calculable — a Poisson's spread is fixed by its mean — so it is subtracted. Over the 532 forward-seasons of five or more appearances in the shipped data, 38% of the apparent spread is that randomness, and correcting for it takes the prior from 6.9 to 11.1 appearances' worth of evidence. Seasons under five appearances are excluded outright, their rates being dominated by the small denominator.

The normal family cannot do this, because a normal's spread is not implied by its mean. `fit_prior` instead estimates it by pooling how much each entity's observations vary around that entity's own mean, which needs entities appearing more than once and is stored as the prior's third parameter, `sigma_obs`.

**A missing scope fails rather than falling back.** Ask for a prior nobody fitted and you get an error listing what exists, not the next broadest prior. A die built from the forwards prior and one built from the global prior are different answers, and nothing downstream could tell them apart. `list_scopes` lets a caller see what is available so the choice stays theirs.

**Draws outside the 1st and 99th percentiles are dropped before binning.** Without that, an outer face reports the single most extreme draw as its bound — and that bound moves with how many draws you asked for, climbing from 46 to 73 as the count went from a thousand to half a million. Clipping is skipped when there are too few samples for the tails to hold one, so it applies from about a hundred upward. Pass `clip=None` to keep everything.

**Adjacent equal-mass faces can share an integer bound.** A D20 over predicted goals showed faces of `21`, `21-22` and `22`, so 22 goals is an outcome on three faces of twenty. That is the die being honest about a count distribution having fewer distinct values than the die has faces; the weights stay correct.

**Entity type is in the store key** so goals-per-player and goals-per-club can share a store, and `PosteriorSampler` raises rather than shrinking a player toward a club's prior.

## Data

[data/player_seasons.csv](data/player_seasons.csv) holds 2,804 player-seasons of Premier League goals and appearances covering 2021/22 to 2025/26. [tools/wikipedia_squads.py](tools/wikipedia_squads.py) built it from the squad statistics tables of Wikipedia's club-season articles and can rebuild it; [data/README.md](data/README.md) describes the columns and their caveats.

The denominator is appearances rather than minutes, because Wikipedia records minutes on almost no club-season article. A five-minute substitute appearance therefore counts as much as ninety, which widens the fitted priors relative to a per-90 denominator.

## Licence

The software — `die_scouting/`, `examples/`, `tools/` and `tests/` — is MIT, in [LICENSE](LICENSE).

`data/` is not: it derives from Wikipedia, whose text is CC BY-SA 4.0, so the dataset carries the same licence and its own attribution in [data/LICENSE](data/LICENSE). The two are separate works in one tree, which is why a fork may take the library closed-source while the data file keeps its terms. Redistributing the data, modified or not, means keeping that licence and the notices with it.

## Development

```
uv sync
uv run pytest
```
