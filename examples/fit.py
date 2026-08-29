"""Fit priors for a set of scopes and write them to a store — the offline half of the
pipeline, run when the data changes rather than per die.

The scopes fitted are the global one plus one per distinct value of `--scope-column`, less
any named by `--exclude`. Scopes with nothing to estimate from are reported and skipped
rather than stopping the run — no goalkeeper in the shipped dataset has scored, so the
goalkeeper scope is skipped every time.

`--scope-column` defaults to position group, which is the axis a scoring rate actually
varies along; `season_name` and `club_name` are columns of the file but poor scopes, one
pinning the prior to a single year of noise and the other mixing team strength into a
player estimate.

Usage:
    uv run python examples/fit_priors.py
    uv run python examples/fit_priors.py --exclude Goalkeeper Defender --priors data/attackers.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from die_scouting import (
    POSTERIOR_PARAM_NAMES,
    ColumnMap,
    CsvDataAdapter,
    JsonPriorStore,
    UnreadablePriorStore,
    fit_priors,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "player_seasons.csv"
PRIORS = ROOT / "data" / "priors.json"


def describe(scope: dict[str, str]) -> str:
    """Render a scope as `column=value` pairs, or as `global` when it has none."""
    return ", ".join(f"{k}={v}" for k, v in scope.items()) or "global"


def column_map(args) -> ColumnMap:
    """Build the adapter's column map from the command line."""
    return ColumnMap(
        entity=args.entity_column,
        entity_type=args.entity_type,
        denominator=args.denominator_column,
        name=args.name_column,
        dimensions=tuple(args.dimensions),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stat", default="goals")
    parser.add_argument(
        "--model",
        choices=list(POSTERIOR_PARAM_NAMES),
        default="gamma_poisson",
    )
    parser.add_argument("--scope-column", default="position_general")
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="values of --scope-column to leave out of the fit",
    )
    parser.add_argument("--denominator-column", default="appearances")
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
        help="columns priors may be fitted along; --scope-column must name one",
    )
    parser.add_argument("--priors", type=Path, default=PRIORS)
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(f"no data at {args.data}")

    adapter = CsvDataAdapter(args.data, column_map(args))
    try:
        store = JsonPriorStore(args.priors)
    except UnreadablePriorStore as error:
        raise SystemExit(str(error)) from None

    report = fit_priors(
        adapter, store, args.stat, args.model, args.scope_column, args.exclude
    )

    print(f"{args.stat} ({args.model}) -> {args.priors}")
    for scope in report.fitted:
        prior = store.get(args.entity_type, args.stat, scope)
        params = ", ".join(f"{k}={v:.3f}" for k, v in prior.params.items())
        print(f"  fitted   {describe(scope):<40} {params}")
    for scope, reason in report.skipped:
        print(f"  skipped  {describe(scope):<40} {reason}")


if __name__ == "__main__":
    main()
