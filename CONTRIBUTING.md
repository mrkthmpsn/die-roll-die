# Contributing

This document covers how to work on die-roll-die, the decisions behind its current design, and
the directions it might take next. The [README](README.md) covers what the library does and how
to use it.

## Getting set up

The project requires Python 3.11 or later and uses [uv](https://docs.astral.sh/uv/) for
dependencies.

```
uv sync
uv run pytest
```

`uv sync` installs the library in editable mode. The `dev` group includes the `scrape` group, so
it also pulls `requests`, `beautifulsoup4` and `lxml`, which only `tools/wikipedia_squads.py`
uses.

## Running the checks

`pytest` is the only gate — there is no linter or type checker in CI:

```
uv run pytest
```

Every push and pull request runs the suite on Python 3.11, 3.12 and 3.13 on Linux. That job
installs with `uv sync --locked`, which fails if the lock would have to change to satisfy
`pyproject.toml`, and then runs both scripts in `examples/` end to end. A second job builds the
wheel on 3.12 and checks that the `py.typed` marker is inside it.

## Conventions

- **Docstrings and comments** follow [AGENTS.md](AGENTS.md): describe the thing itself — its
  structure, arguments and return — rather than its role in a story about the system.
- **The public API is wider than `__all__`.** The exported names in `die_roll_die/__init__.py`
  are one half; the other is what the library serialises — the fields of
  `Die.model_dump_json()` and the file `JsonPriorStore` writes — because consumers parse both.
  Each carries a `schema_version` to be incremented when a field is renamed, removed, or kept
  while its meaning changes.
- **Tests sit in the file mirroring the module** they cover, with a sentence-long name per test
  describing the behaviour it pins. Seven modules have a mirror; `models.py` and `die.py` are
  covered by `tests/test_imports.py`, which also holds the packaging checks.
- **Type annotations** are a convention rather than a gate: nothing in CI type-checks. The
  package ships a PEP 561 `py.typed` marker, so an installed consumer's checker reads them, which
  is what makes an unannotated addition a visible regression for them rather than for us.

## Submitting a change

1. Work on a branch and open a pull request against `main`. Both CI jobs must pass: the test
   matrix on 3.11, 3.12 and 3.13, and the wheel build.
2. Add tests beside the ones for the module you changed, in the file that mirrors it. Behaviour
   in `examples/` counts: `tests/test_examples.py` exists because two defects reached those
   scripts through the gap where nothing imported them.
3. If you changed dependencies, run `uv lock` and commit the result — CI installs with
   `uv sync --locked`, which fails if the lock does not already satisfy `pyproject.toml`.
4. If you renamed or removed an exported name, update the README and this document with it. Both
   name library functions in prose, and a grep for the old name is the check.
5. If you changed a serialised field, increment the `schema_version` that covers it.

Bug reports and feature suggestions are welcome as issues. Include the version
(`die_roll_die.__version__`), the model you were fitting, and the shape of the data if the
problem involves a fit that failed or produced something unexpected.

## Where the code lives

The library is about 1,450 lines over twelve modules and runs as a chain: a file becomes
observations, observations become a prior, a prior plus one entity's observations become a
posterior, and draws from that posterior become a die. Each module owns one link.

| Module | Responsibility |
| --- | --- |
| `models.py` | The shapes everything else passes around: `Record`, `PriorParams`, `Face`, `Die`. |
| `data_adapter.py`, `csv_adapter.py` | Turn a source into `Record`s. The only modules that know what a CSV is. |
| `prior_discovery.py` | Fit a prior from many entities' records. |
| `prior_store.py` | Save and load fitted priors. |
| `quality_sampler.py` | Update a prior with one entity's records, and draw from the result. |
| `discretizer.py` | Cut a list of draws into weighted faces. |
| `die.py` | Wrap faces and metadata into a `Die`. |
| `pipeline.py` | The routes a caller uses: `fit_priors`, `create_die`, `build_die_from_csv`. |
| `fitting.py` | Run a fit across several scopes, reporting the ones too thin to fit. |
| `errors.py` | The exception types: `PriorFitError` and `SamplingError` with their subclasses, plus `UnreadablePriorStore`. |

The chain splits in two, which is why `PriorStore` exists:

```
Offline (periodic):  DataAdapter (population) -> fit_prior -> PriorStore          [fit_priors]
Online (per roll):   PriorStore + DataAdapter (one entity) -> QualitySampler
                       -> Discretizer -> Die                                     [create_die]
```

Read the modules in the order of the table, starting with `models.py`, since every other module
is written in terms of those four types. `pipeline.py` is the alternative starting point if you
would rather see the whole chain before the parts. The tests are where behaviour is pinned, and
`tests/test_quality_sampler.py` in particular is where each model's update arithmetic is pinned,
which is the thing hardest to read off `quality_sampler.py` itself.

## Design decisions

**Fitting priors and rolling a die are separate steps.** A prior describes a population and does
not change when you ask about a different entity, so `fit_priors` computes it once and writes it
to a `PriorStore`, and `create_die` reads it back. Twenty dice then need one fit rather than twenty.
`build_die_from_csv` combines both for convenience, at the cost of reparsing the file and
refitting the prior on every call: 2.5 seconds against 1.6 over twenty entities on the shipped
data.

**A stored prior is keyed by entity type as well as by stat and scope.** Goals-per-player and
goals-per-club are different populations that would otherwise collide in one store under the same
stat name. Shrinking a player toward a club's average produces a plausible number rather than an
error, so `PosteriorSampler` rejects a prior whose entity type does not match the observations.

**The stat is chosen per call rather than named in the column map.** `ColumnMap` names the columns
filling fixed roles — entity, denominator, label, and the dimensions priors may be fitted along —
and any numeric column can then be the stat, with any column available to filter on. This reduces
overhead when writing the `ColumnMap`.

## Statistical decisions

The library calculates a prior and posterior; and turns the spread of that estimate into the
faces of a die. Several steps in that process involved some choices.

### Priors are fitted by method of moments

Priors are fitted by method of moments (matching the mean and variance of the observed rates to
the distribution's own formulas for its mean and variance, then solving for the parameters). This approach was taken because the arithmetic can be easily followed, which feels more accessible and in keeping with the general aim of demonstrating probabilities with weighted dice.

Although, in this method, rates enter unweighted, `min_denominator` is used to exclude the thinnest observations (e.g. players with fewer than 10 appearances). This, for example, drops 156 of 639 forward-seasons on the shipped data.

### The prior is fitted on a population containing the entity it is applied to

An entity's record is used twice. Haaland's four seasons are among the 483 that reach the forwards
fit, and those same seasons then update the prior they helped set, so he is shrunk toward a mean
that has already moved toward him.

The effect scales with how small the population is: fitted on ten forwards rather than 329, the rate moves by a
median 88.7% depending on whether he is included, 45.6% at twenty, and 9.6% at a hundred.

This is, though, the simplest approach. As for method of moments, this seems most in-keeping with the general demonstrative aim of the repo/project.

### Observations enter only through their sums

The update adds an entity's total value to one parameter and its total denominator to the other,
so nothing else about the record reaches the posterior. Recency, ordering and age cannot enter
the equation. Weighting for recency or age curve is in the [roadmap](#roadmap), but for now an entity's seasons count
equally.

### The model is not something the data can settle

`fit_prior` requires the `model` parameter rather than trying to determine the type programmatically.

Three guards catch part of a wrong choice though. The beta fit rejects a row whose value exceeds its own
denominator, and rejects proportions more spread than any beta with their mean; `gamma_exponential`
rejects a value or count that is not positive. None catches the main case: a 90% free-throw shooter
fitted as `gamma_poisson` gives a die with 21% of its mass above 100 makes from 100 attempts, and
nothing in the output says so.

## Roadmap

Possible directions rather than commitments, listed roughly in order of how much they would
change the numbers the library produces.

- **Recency weights on the posterior update.** One multiplier per observation, applied to both
  its value and its denominator, so an older season moves the posterior less than a recent one
  without asserting the entity was worse at the time.
- **An ageing curve.** Distinct from a recency weight: it holds that the entity's true rate was
  predictably different at that age, and converts the denominator into peak-equivalent exposure
  rather than discounting the evidence.
- **A leave-one-out option on fitting.** Fitting each entity's prior from every other entity,
  removing the double-use of data described under [statistical decisions](#the-prior-is-fitted-on-a-population-containing-the-entity-it-is-applied-to). It only matters on
  small populations, where it matters a great deal.
- **A model adviser that reports evidence rather than choosing.** Given observations, report what
  they rule out — a negative value rules out both gamma models and the beta; values that never
  exceed their denominator are the signature of successes out of attempts — leaving the decision
  with the user, since it cannot distinguish the two gamma models at all.
- **A match-level dataset.** `BootstrapSampler` requires rows finer than whole seasons, and the
  shipped file holds season totals, so the comparison between a shrunk die and an unshrunk one
  cannot be demonstrated on the data included here.
- **An `extra` argument on `create_die`.** So a caller can populate a die's metadata without
  writing to the object after it is returned.
