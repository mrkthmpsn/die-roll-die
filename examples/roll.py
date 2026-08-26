"""Build a die for one entity from a CSV in `data/`, one row per entity per period.

Reads `data/player_seasons.csv`, which ships with the repo: Premier League goals and
appearances per player per season.

Usage:
    uv run python examples/roll.py "Erling Haaland"
    uv run python examples/roll.py "Bukayo Saka" --scope position_general=Forward
    uv run python examples/roll.py "Mohamed Salah" --scope season_name=2024/25 --faces 8
    uv run python examples/roll.py "Cole Palmer" --faces 10 --strategy equal_width
"""

from __future__ import annotations

import argparse
from pathlib import Path

from die_scouting import (
    ColumnMap,
    CsvDataAdapter,
    DieMetadata,
    JsonPriorStore,
    PosteriorSampler,
    PriorFitError,
    build_die,
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


def _prior_pair(prior) -> tuple[float, float]:
    """Return the prior's two parameters in the order `posterior_params` returns them."""
    if prior.family == "normal":
        return prior.params["mu"], prior.params["sigma"]
    return prior.params["alpha"], prior.params["beta"]


def _param_names(family: str) -> tuple[str, str]:
    """Return the names `posterior_params` returns its two values under, for this family."""
    return ("mu", "sigma") if family == "normal" else ("alpha", "beta")


def _summarise(family: str, first: float, second: float) -> str:
    """Describe a family's two parameters as the quantity they imply."""
    if family == "gamma":
        return f"{first / second:.3f} per unit (worth {second:.1f} of denominator)"
    if family == "beta":
        return f"{first / (first + second):.3f} of attempts (worth {first + second:.1f} attempts)"
    return f"{first:.3f} per unit, spread {second:.3f}"


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
    store = JsonPriorStore(path)
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
    parser.add_argument("player", help="part of a player's name, matched case-insensitively")
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
        "--family",
        choices=["beta", "gamma", "normal"],
        default="gamma",
        help="prior distribution family for this stat",
    )
    parser.add_argument(
        "--strategy", choices=["equal_mass", "equal_width"], default="equal_mass"
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
            "no dataset ships with this repo; put a CSV of one row per entity per period "
            "there, or point this script at your own"
        )
    adapter = CsvDataAdapter(DATA, column_map(args))
    scope = parse_scope(args.scope)

    matches = adapter.entity_ids_for_name(args.player)
    if not matches:
        raise SystemExit(f"no player matching {args.player!r}")
    entity_id = matches[0]

    if args.priors:
        prior = read_prior(args.priors, args.entity_type, args.stat, scope)
    else:
        try:
            prior = fit_prior(
                adapter.get_population_observations(args.stat, scope),
                args.family,
                args.stat,
                scope,
            )
        except PriorFitError as error:
            raise SystemExit(
                f"cannot fit a {args.family} prior for {args.stat!r}: {error}\n"
                "try a different --family, a broader --scope, or a different "
                "--denominator-column"
            ) from None
    sampler = PosteriorSampler(prior, adapter, args.stat)
    observations = adapter.get_entity_observations(entity_id, args.stat, scope)
    alpha, beta = sampler.posterior_params(entity_id)

    metadata = DieMetadata(
        entity_id=entity_id,
        entity_type=args.entity_type,
        entity_name=adapter.entity_name(entity_id) or args.player,
        stat_id=args.stat,
        scope=scope,
        prior=prior,
        posterior_params=dict(zip(_param_names(prior.family), (alpha, beta))),
        observed_value=sum(o.value for o in observations),
        observed_denominator=sum(o.denominator for o in observations),
        predicted_denominator=args.denominator,
        denominator_unit=args.denominator_column,
        extra={"seasons": len(observations)},
    )

    samples = sampler.sample_predictive(entity_id, args.draws, args.denominator)
    die = build_die(samples, n_faces=args.faces, metadata=metadata, strategy=args.strategy)
    meta = die.metadata

    print(f"{meta.entity_name} ({meta.entity_id}) - {meta.stat_id}, scope {meta.scope or 'none'}")
    print(
        f"  record:    {meta.observed_value:.0f} in {meta.observed_denominator:.1f} "
        f"{meta.denominator_unit} across {meta.extra['seasons']} seasons"
    )
    family = meta.prior.family
    posterior = tuple(meta.posterior_params[name] for name in _param_names(family))
    print(f"  prior:     {family}, {_summarise(family, *_prior_pair(meta.prior))}")
    print(f"  posterior: {_summarise(family, *posterior)}")

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
