# Contributing

## Working on it

```
uv sync
uv run pytest
```

Docstring and comment conventions are in [AGENTS.md](AGENTS.md): describe the thing itself —
its structure, arguments and return — rather than its role in a story about the system.

Every push runs the suite on Python 3.11, 3.12 and 3.13 on Linux, installs with
`uv sync --frozen` so a lock that has drifted from `pyproject.toml` fails, and runs both
example scripts end to end.

## Why it is built this way

**A prior is fitted once and stored, not recomputed per die.** `fit_priors` writes to a
`PriorStore` and `create_die` reads from it, so building dice for twenty entities fits one
prior rather than twenty. `build_die_from_csv` collapses both into a call for convenience and
pays for it: it reparses the file and refits the prior every time.

**Entity type is part of the store key**, so goals-per-player and goals-per-club can live in
one store, and `PosteriorSampler` raises rather than shrinking a player toward a club's prior.

**The stat is chosen per call, not mapped.** `ColumnMap` names the entity, denominator, label
and dimension columns; any numeric column can then be the stat, and any column at all can be
filtered on, so one adapter serves every question a file can answer.

## Statistical choices, and what each one costs

The library makes choices a reader with statistical training would want stated. Each of these
is a position rather than an oversight, and each has a cost.

**Priors are fitted by method of moments.** The gamma has two parameters, its mean is
`alpha/beta` and its variance is `alpha/beta²`, so the fit computes the mean and variance of
the observed per-entity rates and solves the two equations. The conventional alternative is
marginal maximum likelihood: write the probability of the whole dataset given a candidate
`alpha` and `beta` — for a gamma-Poisson, each entity's count follows a negative binomial once
its own rate is integrated out — and search for the pair that makes the data most probable.

Method of moments is arithmetic a reader can follow on the page, which is the point of a
library that exists to show how the estimate is made; marginal maximum likelihood puts the fit
inside an optimiser and a dependency. The cost is that it is handed one rate per observation
however much exposure stands behind it, so a ten-appearance season and a thirty-eight-appearance
season count equally. Two features exist to repair that: `min_denominator` drops observations
too thin to carry a meaningful rate, and the Poisson sampling variance is subtracted from the
observed spread so that only genuine between-entity differences reach the prior. On the shipped
data that correction accounts for 34% of the apparent spread, taking the forwards prior from
7.5 to 11.4 appearances' worth of evidence.

`normal_normal` cannot make that correction, a normal's spread not being implied by its mean,
so `fit_prior` estimates it by pooling how much each entity's observations vary around that
entity's own mean and stores it as the third parameter, `sigma_obs`.

**A prior is fitted on a population that includes the entity it is then used on.** Haaland's
four seasons are among the 639 that fit the forwards prior, so his own record helps set the
mean he is shrunk toward — the double-use of data that empirical Bayes is known for, whose
textbook fix is to leave the entity out and fit the rest.

On the shipped data this is a rounding error: leaving him out moves the prior's rate from
0.197 to 0.192 and his die from 23.90 to 23.61 goals over 30 appearances, a 1.2% shift, and
Saka's die does not move at two decimal places. It scales with how small the population is —
fitted on ten forwards rather than 329, the prior's rate moves by a median 88.7% depending on
whether the entity is in it, 45.6% at twenty and 9.6% at a hundred. The default stays as it is
because fitting one prior and reusing it is what `PriorStore` is for, and leaving one entity
out means a prior per entity. Worth knowing if you point this at a file of a dozen rows.

**Observations are exchangeable.** An entity's seasons are summed without weighting, so a
season from four years ago counts as much as the most recent one, and no ageing curve adjusts
for the age an entity was when it recorded them. Both are known omissions rather than
assumptions that the data supports.

**The model is the caller's to choose.** A stat-type router that picked one was removed,
because the model states which values a stat can take at all and no sample establishes that:
an unobserved value and an impossible one look identical in data. Fitting a 90% free-throw
shooter as `gamma_poisson` runs without complaint and puts 21% of the die above 100 made out
of 100 attempted.

## Ideas that might be fun to add

No commitment to any of these; they are the directions that seemed worth having if the project
goes further.

- **Recency weights on the posterior update.** One multiplier per observation applied to both
  its value and its denominator, so a four-year-old season moves the posterior less than last
  season without asserting the entity was worse then.
- **An ageing curve.** Different from a recency weight: it says the entity's true rate was
  predictably different at that age, converting the denominator into peak-equivalent exposure
  rather than discounting the evidence. Within-entity comparison on the shipped data puts the
  peak at 25-26 with decline arriving at 32.
- **A model adviser that reports evidence rather than choosing.** Given observations, say what
  they rule out — any negative value rules out both gamma models and the beta; values never
  exceeding their denominator is the signature of successes out of attempts — and leave the
  choice with the person, since it cannot tell the two gamma models apart at all.
- **A leave-one-out option on fitting**, for the small-population case above.
- **A match-level dataset.** `BootstrapSampler` wants rows finer than seasons, and the shipped
  file is season totals, so the comparison between a shrunk die and an unshrunk one cannot be
  demonstrated on what ships here.
- **An `extra` argument on `create_die`**, so a caller can put something in the metadata
  without writing onto the returned object.
