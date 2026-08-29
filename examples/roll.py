"""Build a die for one entity from a CSV in `data/`, one row per entity per period.

Takes an entity id rather than a name, a name being no kind of identifier: "Saka" matches
Aaron Wan-Bissaka as readily as Bukayo Saka.

Reads `data/player_seasons.csv`, which ships with the repo: Premier League goals and
appearances per player per season.

Usage:
    uv run python examples/roll.py Erling_Haaland
    uv run python examples/roll.py Bukayo_Saka --scope position_general=Forward
    uv run python examples/roll.py Mohamed_Salah --scope season_name=2024/25 --faces 8
    uv run python examples/roll.py Cole_Palmer --faces 10 --strategy equal_width
"""

from __future__ import annotations

import argparse
from pathlib import Path

from die_roll_die import (
    POSTERIOR_PARAM_NAMES,
    ColumnMap,
    CsvDataAdapter,
    JsonPriorStore,
    PriorFitError,
    UnreadablePriorStore,
    UnsuitableDenominator,
    create_die,
    fit_prior,
)

DATA = Path(__file__).resolve().parent.parent / "data" / "player_seasons.csv"


def parse_scope(pairs: list[str]) -> dict[str, str]:
    """Parse `column=value` strings into a scope dict."""
    scope = {}
    for pair in pairs:
        column, _, value = pair.partition("=")
        if not value:
            raise SystemExit(f"scope must be given as column=value; got {pair!r}")
        scope[column] = value
    return scope


def _summarise(model: str, first: float, second: float, stat: str, unit: str) -> str:
    """Describe a model's two parameters as the quantity they imply, in the caller's own
    column names: how much of `stat` per unit of `unit`, and how much evidence that rests on.
    """
    if model == "gamma_poisson":
        return f"{first / second:.3f} {stat}/{unit}, worth {second:.1f} {unit} of evidence"
    if model == "gamma_exponential":
        return f"{second / first:.3f} {stat}/{unit}, worth {first:.1f} {unit} of evidence"
    if model == "beta_binomial":
        share = first / (first + second)
        return f"{share:.3f} {stat}/{unit}, worth {first + second:.1f} {unit} of evidence"
    if model == "normal_normal":
        return f"mean {first:.3f} {stat}/{unit}, spread {second:.3f}"
    raise ValueError(f"no summary written for a {model} prior")


def column_map(args) -> ColumnMap:
    """Build the adapter's column map from the command line."""
    return ColumnMap(
        entity=args.entity_column,
        entity_type=args.entity_type,
        denominator=args.denominator_column,
        name=args.name_column,
        dimensions=tuple(args.dimensions),
    )


def read_prior(path: Path, entity_type: str, stat_id: str, scope: dict[str, str]):
    """Return the stored prior for this entity type, stat and scope, or exit listing what
    is stored.
    """
    try:
        store = JsonPriorStore(path)
    except UnreadablePriorStore as error:
        raise SystemExit(str(error)) from None
    prior = store.get(entity_type, stat_id, scope)
    if prior is not None:
        return prior
    available = store.list_scopes(entity_type, stat_id)
    listed = "\n".join(f"  {s or 'global'}" for s in available) or "  (none)"
    raise SystemExit(
        f"{path} holds no prior for {stat_id!r} scoped to {scope or 'global'}\n"
        f"scopes fitted for {stat_id!r}:\n{listed}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entity", help="the entity id to roll for, e.g. Bukayo_Saka")
    parser.add_argument("--stat", default="goals")
    parser.add_argument("--scope", nargs="*", default=[], help="column=value, repeatable")
    parser.add_argument(
        "--denominator", type=float, default=30.0, help="how much denominator to predict over"
    )
    parser.add_argument(
        "--denominator-column",
        default="appearances",
        help="column the stat is measured against; attempts rather than time for a beta",
    )
    parser.add_argument("--entity-column", default="player_source_id")
    parser.add_argument(
        "--entity-type",
        default="player",
        help="what the entity column identifies; priors are stored per type",
    )
    parser.add_argument("--name-column", default="player_name")
    parser.add_argument(
        "--dimensions",
        nargs="*",
        default=["club_name", "season_name", "position_general"],
        help="columns priors may be fitted along, carried onto each observation",
    )
    parser.add_argument("--faces", type=int, default=6)
    parser.add_argument(
        "--model",
        choices=list(POSTERIOR_PARAM_NAMES),
        default="gamma_poisson",
        help="the conjugate pair to fit and update with; see the README",
    )
    parser.add_argument(
        "--strategy",
        choices=["equal_weight", "equal_width"],
        default="equal_width",
        help=(
            "equal_width gives every face the same range of values and different chances, "
            "a weighted die; equal_weight gives every face the same chance and different "
            "ranges, an unweighted die with uneven faces"
        ),
    )
    parser.add_argument(
        "--priors",
        type=Path,
        help="read the prior from this store instead of fitting it from the population",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the Die as JSON instead of as faces"
    )
    parser.add_argument("--draws", type=int, default=100_000)
    args = parser.parse_args()

    if not DATA.exists():
        raise SystemExit(
            f"no data at {DATA}\n"
            "the shipped dataset lives there; restore it, or point the column flags at a "
            "CSV of your own"
        )
    adapter = CsvDataAdapter(DATA, column_map(args))
    scope = parse_scope(args.scope)

    entity_id = args.entity
    name = adapter.entity_name(entity_id)
    if name is None:
        raise SystemExit(f"no entity with id {entity_id!r} in {DATA.name}")

    if args.priors:
        prior = read_prior(args.priors, args.entity_type, args.stat, scope)
    else:
        try:
            prior = fit_prior(
                adapter.get_population_observations(args.stat, scope),
                args.model,
                args.stat,
                scope,
            )
        except PriorFitError as error:
            raise SystemExit(
                f"cannot fit a {args.model} prior for {args.stat!r}: {error}\n"
                "try a different --model, a broader --scope, or a different "
                "--denominator-column"
            ) from None
    try:
        die = create_die(
            adapter,
            prior,
            entity_id,
            args.denominator,
            n_faces=args.faces,
            strategy=args.strategy,
            draws=args.draws,
            entity_name=name,
            denominator_unit=args.denominator_column,
        )
    except UnsuitableDenominator as error:
        raise SystemExit(f"--denominator {args.denominator:g}: {error}") from None
    meta = die.metadata

    print(f"{meta.entity_name} ({meta.entity_id}) - {meta.stat_id}, scope {meta.scope or 'none'}")
    print(
        f"  record:    {meta.observed_value:.0f} in {meta.observed_denominator:.1f} "
        f"{meta.denominator_unit} across {meta.observed_periods} seasons"
    )
    model = meta.prior.model
    posterior = tuple(meta.posterior_params[param] for param in POSTERIOR_PARAM_NAMES[model])
    units = (meta.stat_id, meta.denominator_unit)
    print(f"  prior:     {model}, {_summarise(model, *meta.prior.ordered_params, *units)}")
    print(f"  posterior: {_summarise(model, *posterior, *units)}")

    if args.json:
        print()
        print(die.model_dump_json(indent=2))
        return

    print(f"\n  a D{args.faces} ({meta.strategy}) over {meta.stat_id} "
          f"in the next {meta.predicted_denominator:.0f} {meta.denominator_unit}:")
    for face in die.faces:
        low, high = face.value_range
        places = 0 if low == int(low) and high == int(high) else 1
        span = f"{low:.{places}f}" if low == high else f"{low:.{places}f}-{high:.{places}f}"
        print(f"    {face.label:>3}  {span:>9}  {face.weight:6.1%}")


if __name__ == "__main__":
    main()
