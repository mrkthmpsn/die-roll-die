from __future__ import annotations

from typing import Protocol

from .models import PriorParams


class PriorStore(Protocol):
    """Persists discovered priors, keyed by (stat_id, scope)."""

    def save(self, params: PriorParams) -> None: ...

    def get(self, stat_id: str, scope: dict[str, str]) -> PriorParams | None:
        """Exact lookup only — no fallback. Fallback lives in `resolve_prior`."""
        ...


def resolve_prior(store: PriorStore, stat_id: str, scope: dict[str, str]) -> PriorParams:
    """Look up the most specific prior matching `scope`, falling back to progressively
    broader scopes and finally the global (unscoped) prior.

    Raises if no prior has been discovered for this stat at any scope, including global.
    """
    raise NotImplementedError
