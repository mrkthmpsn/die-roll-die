"""Build a goals die for one Premier League player from the extract in `data/`.

Usage:
    uv run python examples/roll.py "Harry Kane"
    uv run python examples/roll.py "Kevin De Bruyne" --stat assists --scope position_general=Midfielder
    uv run python examples/roll.py "Peter Crouch" --stat headed_shots --denominator-column shots --family beta
"""

from __future__ import annotations

import argparse
from pathlib import Path

from die_scouting import AnalyticSource, CsvDataAdapter, PriorFitError, build_die, fit_prior

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


def _summarise(family: str, first: float, second: float) -> str:
    """Describe a family's two parameters as the quantity they imply."""
    if family == "gamma":
        return f"{first / second:.3f} per unit (worth {second:.1f} of denominator)"
    if family == "beta":
        return f"{first / (first + second):.3f} of attempts (worth {first + second:.1f} attempts)"
    return f"{first:.3f} per unit, spread {second:.3f}"


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
        default="nineties",
        help="column the stat is measured against; attempts rather than time for a beta",
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
    parser.add_argument("--draws", type=int, default=100_000)
    args = parser.parse_args()

    adapter = CsvDataAdapter(DATA, denominator_column=args.denominator_column)
    scope = parse_scope(args.scope)

    matches = adapter.entity_ids_for_name(args.player)
    if not matches:
        raise SystemExit(f"no player matching {args.player!r}")
    entity_id = matches[0]

    try:
        prior = fit_prior(
            adapter.get_population_observations(args.stat, scope), args.family, args.stat, scope
        )
    except PriorFitError as error:
        raise SystemExit(
            f"cannot fit a {args.family} prior for {args.stat!r}: {error}\n"
            "try a different --family, a broader --scope, or a different "
            "--denominator-column"
        ) from None
    source = AnalyticSource(prior, adapter, args.stat)
    observations = adapter.get_entity_observations(entity_id, args.stat, scope)
    alpha, beta = source.posterior_params(entity_id)

    name = observations[0].context["player_name"] if observations else args.player
    recorded = sum(o.value for o in observations)
    played = sum(o.denominator for o in observations)

    print(f"{name} ({entity_id}) - {args.stat}, scope {scope or 'none'}")
    print(
        f"  record:    {recorded:.0f} in {played:.1f} {args.denominator_column} "
        f"across {len(observations)} seasons"
    )
    print(f"  prior:     {prior.family}, {_summarise(prior.family, *_prior_pair(prior))}")
    print(f"  posterior: {_summarise(prior.family, alpha, beta)}")

    samples = source.sample_predictive(entity_id, args.draws, args.denominator)
    die = build_die(
        samples,
        n_faces=args.faces,
        metadata={"entity_id": entity_id, "strategy": args.strategy},
        strategy=args.strategy,
    )

    print(f"\n  a D{args.faces} ({args.strategy}) over {args.stat} "
          f"in the next {args.denominator:.0f} {args.denominator_column}:")
    for face in die.faces:
        low, high = face.value_range
        places = 0 if low == int(low) and high == int(high) else 1
        span = f"{low:.{places}f}" if low == high else f"{low:.{places}f}-{high:.{places}f}"
        print(f"    {face.label:>3}  {span:>9}  {face.weight:6.1%}")


if __name__ == "__main__":
    main()
