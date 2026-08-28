# die-scouting

die-scouting is a demonstration of probabilistic statistics. It takes a set of statistics — for example, a footballer's goals across several seasons — works out a distribution of what that player's underlying scoring rate might be, and turns that distribution into a weighted die.

A prior is fitted from a population's data (e.g. what forwards in general score) and updated with the player's own record to give a posterior over their true rate. To make this easier to conceptualise, the posterior can be turned into a virtual die, to be virtually rolled with results reflecting the probabilities of the data.

The repo includes five seasons of Premier League goals and appearances data taken from Wikipedia, but the underlying framework can be used with a your own dataset(s).

## Example
Using the Wikipedia data, here is a die for Erling Haaland's goals over his next 30 appearances, scoped against the prior distribution of forwards in the dataset:

```
$ uv run python examples/roll.py Erling_Haaland --scope position_general=Forward --priors data/priors.json

Erling Haaland (Erling_Haaland) - goals, scope {'position_general': 'Forward'}
  record:    112 goals in 132.0 appearances across 4 seasons
  prior:     gamma, 0.197 goals/appearances, worth 11.4 appearances of evidence
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

## Try it

```
uv sync
uv run python examples/fit_priors.py
uv run python examples/roll.py Bukayo_Saka --scope position_general=Forward --priors data/priors.json
```

The first command fits a prior for each position group and writes them to `data/priors.json`; the second builds a die for one player. A dataset of 2,804 Premier League player-seasons ships with the repo, so both work on a fresh clone.

Useful flags on `roll.py`: `--faces 20` for a D20, `--denominator 38` to predict over a full 38-appearance season, `--strategy equal_width` for the histogram view.

## What you can point it at

Football is used as an example, but the library is built around the shape of the measurement. There are three shapes it handles, and your data decides which one you have:

**A count over an 'exposure'.** Goals in appearances, tackles in minutes, defects in production hours, support tickets in weeks on the team. You choose how much exposure to predict over — 30 appearances, 900 minutes — and the die is over how many events fall in it.

**Successes out of attempts.** Shots on target out of shots, passes completed out of attempted, free throws made out of taken. You choose how many attempts, and the die is over how many of them come off.

**A measured quantity.** Distance covered per match, revenue per week, hours of downtime per month. You choose how many periods, and the die is over the total across them — so this shape wants quantities that add up to something meaningful.

A composite score — an "inverted full-back suitability out of 10" computed however you like — is consumed rather than modelled here: work out the score per match by whatever formula you please, and feed the scores in as the stat. Note that a score bounded at 0 and 10 is a beta after rescaling to 0-1, not a normal, and that the die will be over the total across the periods you choose rather than the average.

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

**A prior** is what you believe about a player before looking at their record — here, what scoring rates Premier League forwards have in general. It is not hand-picked: `fit_prior` reads every forward-season in the file and fits a distribution to the spread of their rates. For goals it comes out as `alpha=2.26, beta=11.44`, which describes a typical forward scoring 0.20 goals per appearance.

**`beta` is evidence measured in appearances**: this prior is worth about 11 appearances of watching someone play, which is what sets how far a player's own record can move it.

**The posterior** is the prior updated with one player's own record, and for this family the update is two additions:

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

**The prior fit corrects for noise in its own inputs.** A season's goals-per-appearance is spread by two things: how much players genuinely differ, and the randomness of scoring itself. Only the first belongs in a prior. For counts the second is calculable — a Poisson's spread is fixed by its mean — so it is subtracted. Over the 483 forward-seasons of ten or more appearances in the shipped data, 34% of the apparent spread is that randomness, and correcting for it takes the prior from 7.5 to 11.4 appearances' worth of evidence. Seasons under ten appearances are excluded outright, their rates being dominated by the small denominator — and the threshold is a modelling choice, since a prior over any forward would include everybody while a prior over a forward who plays should not.

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
