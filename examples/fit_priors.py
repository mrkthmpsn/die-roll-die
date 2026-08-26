"""Fit priors for a set of scopes and write them to a store — the offline half of the
pipeline, run when the data changes rather than per die.

The scopes fitted are the global one plus one per distinct value of `--scope-column`, less
any named by `--exclude`, which defaults to Goalkeeper because no goalkeeper in the shipped
dataset has scored. Scopes with too little data to fit are reported and skipped.

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

from die_scouting import CsvDataAdapter, JsonPriorStore, fit_scopes, scopes_for

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "player_seasons.csv"
PRIORS = ROOT / "data" / "priors.json"


def describe(scope: dict[str, str]) -> str:
    """Render a scope as `column=value` pairs, or as `global` when it has none."""
    return ", ".join(f"{k}={v}" for k, v in scope.items()) or "global"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stat", default="goals")
    parser.add_argument("--family", choices=["beta", "gamma", "normal"], default="gamma")
    parser.add_argument("--scope-column", default="position_general")
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=["Goalkeeper"],
        help=(
            "values of --scope-column to skip; goalkeepers score no goals, so no gamma "
            "fits them. Pass --exclude with no values to fit every scope"
        ),
    )
    parser.add_argument("--denominator-column", default="appearances")
    parser.add_argument("--priors", type=Path, default=PRIORS)
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(f"no data at {args.data}")

    adapter = CsvDataAdapter(args.data, denominator_column=args.denominator_column)
    store = JsonPriorStore(args.priors)

    scopes = [{}] + [
        scope
        for scope in scopes_for(adapter, args.stat, args.scope_column)
        if scope[args.scope_column] not in args.exclude
    ]
    report = fit_scopes(adapter, store, args.stat, args.family, scopes)

    print(f"{args.stat} ({args.family}) -> {args.priors}")
    for scope in report.fitted:
        prior = store.get(args.stat, scope)
        params = ", ".join(f"{k}={v:.3f}" for k, v in prior.params.items())
        print(f"  fitted   {describe(scope):<40} {params}")
    for scope, reason in report.skipped:
        print(f"  skipped  {describe(scope):<40} {reason}")


if __name__ == "__main__":
    main()
