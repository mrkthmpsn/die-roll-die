# Contributing

This file is for someone who wants to read the code rather than only use it — to change it, to
check it, or to decide whether it does what they need. The [README](README.md) shows what the
library produces and how to point it at your own data; this one covers how the code is arranged,
which judgement calls sit inside it, and what those calls cost.

## Working on it

```
uv sync
uv run pytest
```

Docstring and comment conventions are in [AGENTS.md](AGENTS.md): describe the thing itself —
its structure, arguments and return — rather than its role in a story about the system.

Every push runs the suite on Python 3.11, 3.12 and 3.13 on Linux, installs with
`uv sync --frozen` so a lock that has drifted from `pyproject.toml` fails, and runs both example
scripts end to end.

## Where to start reading

The library is about 1,450 lines over twelve modules and runs as a chain: a file becomes
observations, observations become a prior, a prior plus one entity's observations become a
posterior, and draws from that posterior become a die. Each module owns one link.

The chain splits in two, and the split is why `PriorStore` exists:

```
Offline (periodic):  DataAdapter (population) -> fit_prior -> PriorStore          [fit_priors]
Online (per roll):   PriorStore + DataAdapter (one entity) -> QualitySampler
                       -> Discretizer -> Die                                     [create_die]
```

| Module | What it does |
| --- | --- |
| `models.py` | The shapes everything else passes around: `Record`, `PriorParams`, `Face`, `Die`. |
| `data_adapter.py`, `csv_adapter.py` | Turn a source into `Record`s. The only modules that know what a CSV is. |
| `prior_discovery.py` | Fit a prior from many entities' records. |
| `prior_store.py` | Save and load fitted priors. |
| `quality_sampler.py` | Update a prior with one entity's records, and draw from the result. |
| `discretizer.py` | Cut a list of draws into weighted faces. |
| `die.py` | Wrap faces and metadata into a `Die`. |
| `pipeline.py` | The routes a caller actually uses: `fit_priors`, `create_die`, `build_die_from_csv`. |
| `fitting.py` | Run a fit across several scopes, reporting the ones too thin to fit. |
| `errors.py` | The exception types, in two trees: fitting and sampling. |

That order is a reasonable read, `models.py` first because every other module is written in
terms of those four types. Start at `pipeline.py` instead if you would rather see the whole
chain before the parts.

The tests mirror the modules one for one and are where the behaviour is pinned: 187 of them,
most a few lines under a sentence-long name. To find out what a function is meant to do, its
test file is usually a faster answer than its implementation.

## Why the code is arranged this way

Three arrangements look arbitrary until you know what they are for, and each comes up within a
few minutes of reading.

**Fitting and rolling are separate steps.** A prior describes a population — what forwards in
general score — and does not change when you ask about a different player, so `fit_priors`
computes it once and writes it to a `PriorStore`, and `create_die` reads it back. Dice for
twenty players then need one fit rather than twenty. `build_die_from_csv` does both in a single
call for convenience and pays for it each time, reparsing the file and refitting the prior, which
is about seven times slower over twenty players.

**A stored prior is keyed by entity type as well as by stat and scope.** Goals-per-player and
goals-per-club are different populations that would otherwise collide in one store under the same
stat name, and shrinking a player toward a club's average is the kind of mistake that produces a
plausible number rather than an error — so `PosteriorSampler` refuses when the two disagree.

**The stat is chosen per call, not named in the column map.** `ColumnMap` names the columns
filling fixed roles — which entity a row belongs to, what its value was measured against, a
label, and the columns you might fit separate priors along — and any numeric column can then be
the stat, with any column at all available to filter on. One adapter therefore answers every
question a file can support, rather than one adapter per stat.

## The statistics, and the choices inside them

What the library does statistically, in short: it estimates how much entities of one kind differ
from each other, which is the **prior**; it combines that with one entity's own record to get a
better estimate for them than either source gives alone, which is the **posterior**; and it turns
the spread of that estimate into the faces of a die.

Four steps in that involved a decision with a genuine alternative. None is hidden — they are all
visible in the code — but none announces itself either, so each is written out here with what it
costs. This is the section to read if you want to know whether the library is doing something you
disagree with.

### Priors are fitted by method of moments

**What that means.** A gamma distribution has two parameters, `alpha` and `beta`; its average is
`alpha/beta` and its spread is `alpha/beta²`. So you compute the average and the spread of the
rates actually observed across entities, set them equal to those two formulas, and solve for the
parameters. Two equations and some algebra, in one pass over the data.

**The alternative.** Marginal maximum likelihood asks, for a candidate `alpha` and `beta`, how
probable the observed dataset would be, and searches for the pair making it most probable. It is
the more conventional choice and uses more of the data: rather than reducing each entity to a
single rate, it works from the counts and the exposures behind them.

**Why the simpler one.** This library exists to show how an estimate is made. Method of moments
is arithmetic a reader can follow on the page, where marginal maximum likelihood puts the fit
inside an optimiser, and the optimiser inside a dependency.

**What it costs.** Method of moments gets one rate per observation however much evidence stands
behind that rate, so a ten-appearance season and a thirty-eight-appearance season count equally.
Two features repair that. `min_denominator` drops observations too thin for their rate to mean
anything, and the Poisson sampling noise is subtracted from the observed spread, so that what
reaches the prior is how much entities genuinely differ rather than how much scoring wobbles by
chance. On the shipped data that correction accounts for 34% of the apparent spread, taking the
forwards prior from 7.5 to 11.4 appearances' worth of evidence.

`normal_normal` cannot make the same correction, because a normal distribution's spread is not
implied by its average the way a Poisson's is. `fit_prior` estimates it instead by pooling how
much each entity's observations vary around that entity's own average, storing it as a third
parameter, `sigma_obs`.

### A prior is fitted on a population that includes the entity it is used on

Haaland's four seasons are among the 639 that fit the forwards prior, so his own record helps set
the average he is then shrunk toward. This is the double-use of data that **empirical Bayes** —
estimating a prior from the same data you then apply it to — is known for, and the textbook fix
is to leave the entity out and fit the prior from everyone else.

**What it costs here.** On the shipped data, very little: leaving him out moves the prior's rate
from 0.197 to 0.192 and his die from 23.90 to 23.61 goals over 30 appearances, a 1.2% shift,
while Saka's die does not move at two decimal places. It scales with how small the population is.
Fitted on ten forwards rather than 329, the prior's rate moves by a median 88.7% depending on
whether the entity is in it; 45.6% at twenty forwards, and 9.6% at a hundred.

**Why it stays.** Fitting one prior and reusing it is what `PriorStore` exists for, and leaving
one entity out means one prior per entity, which is a different pipeline rather than a flag. If
you point this at a file of a dozen rows, the effect is there and worth knowing about.

### An entity's observations are treated as interchangeable

`PosteriorSampler` sums an entity's values and denominators, so a season from four years ago
counts exactly as much as the most recent one, and nothing adjusts for how old the entity was
when it recorded them. Both are omissions rather than positions the data supports. A recency
weight and an ageing curve are in the ideas below, and they would enter the arithmetic at
different points.

### The model is the caller's to choose

`fit_prior` takes `model` as an argument, and no function picks one for you. An earlier version
had a table mapping stat names to models and it was removed, because a model states which values
a stat can take *at all* — whether zero is reachable, whether there is a ceiling — and no sample
establishes that. A value that never appeared and a value that cannot appear look identical in
data.

**What it costs.** Choosing wrong runs without complaint. Fit a 90% free-throw shooter as
`gamma_poisson` rather than `beta_binomial` and everything works, but a gamma has no ceiling, so
21% of the resulting die describes making more than 100 shots out of 100 attempts. Two guards
catch part of it: the beta fit rejects a row whose value exceeds its own denominator, and the
gamma-exponential fit rejects a value or denominator that is not positive.

## Ideas that might be fun to add

Nothing here is committed to. They are the directions that seemed worth having if the project
goes further.

- **Recency weights on the posterior update.** One multiplier per observation applied to both its
  value and its denominator, so a four-year-old season moves the posterior less than last season
  without asserting the entity was worse back then.
- **An ageing curve.** Different from a recency weight: it says the entity's true rate was
  predictably different at that age, so it converts the denominator into peak-equivalent exposure
  rather than discounting the evidence. Comparing players against their own career average on the
  shipped data puts the peak at 25-26, with decline arriving at 32.
- **A model adviser that reports evidence rather than choosing.** Given observations, say what
  they rule out — a negative value rules out both gamma models and the beta; values that never
  exceed their denominator are the signature of successes out of attempts — and leave the
  decision with the person, since it cannot tell the two gamma models apart at all.
- **A leave-one-out option on fitting**, for the small-population case above.
- **A match-level dataset.** `BootstrapSampler` wants rows finer than whole seasons, and the
  shipped file is season totals, so the comparison between a shrunk die and an unshrunk one cannot
  be demonstrated on what ships here.
- **An `extra` argument on `create_die`**, so a caller can put something in a die's metadata
  without writing onto the object after it is returned.
