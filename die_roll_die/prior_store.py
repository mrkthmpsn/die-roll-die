from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .errors import UnreadablePriorStore
from .models import PriorParams


PRIOR_STORE_SCHEMA_VERSION: int = 1
"""The version of the file shape `JsonPriorStore` writes, carried in it as `schema_version`.

Incremented when the file's shape changes: a renamed or removed field of a stored prior, or
a change to how the priors are laid out. A file stating any other version raises
`UnreadablePriorStore` on load rather than being read as this one.
"""


class PriorStore(Protocol):
    """Persists discovered priors, keyed by (entity_type, stat_id, scope)."""

    def save(self, params: PriorParams) -> None: ...

    def get(
        self, entity_type: str, stat_id: str, scope: dict[str, str]
    ) -> PriorParams | None:
        """Return the prior stored for exactly this entity type, stat and scope, or None."""
        ...

    def list_scopes(self, entity_type: str, stat_id: str) -> list[dict[str, str]]:
        """Return the scopes held for this entity type and stat, most dimensions first."""
        ...


def _key(entity_type: str, stat_id: str, scope: dict[str, str]) -> str:
    """Return a key for `entity_type`, `stat_id` and `scope` that does not depend on the
    scope's key order, so the same dimensions saved in either order address one entry.
    """
    return json.dumps([entity_type, stat_id, sorted(scope.items())], separators=(",", ":"))


def _sorted_scopes(scopes: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(scopes, key=lambda scope: (-len(scope), sorted(scope.items())))


class InMemoryPriorStore:
    """Holds priors in a dict for the life of the process."""

    def __init__(self) -> None:
        self._priors: dict[str, PriorParams] = {}

    def save(self, params: PriorParams) -> None:
        """Store `params`, replacing any prior held for the same entity type, stat and
        scope.
        """
        self._priors[_key(params.entity_type, params.stat_id, params.scope)] = params

    def get(
        self, entity_type: str, stat_id: str, scope: dict[str, str]
    ) -> PriorParams | None:
        """Return the prior stored for exactly this entity type, stat and scope, or None."""
        return self._priors.get(_key(entity_type, stat_id, scope))

    def list_scopes(self, entity_type: str, stat_id: str) -> list[dict[str, str]]:
        """Return the scopes held for this entity type and stat, most dimensions first."""
        return _sorted_scopes([
            p.scope
            for p in self._priors.values()
            if p.stat_id == stat_id and p.entity_type == entity_type
        ])


class JsonPriorStore:
    """Holds priors in a JSON file, read on construction and rewritten on every save.

    The file is `{"schema_version": PRIOR_STORE_SCHEMA_VERSION, "priors": [...]}`, the
    priors being a list of serialised `PriorParams`. Each carries the entity type, stat and
    scope it is keyed by, so the lookup key `get` uses is rebuilt on load rather than
    written down.

    A path that does not exist is an empty store, so a first run needs no setup. Each save
    rewrites the whole file, so a run that stops partway keeps the priors already saved.

    Raises:
        UnreadablePriorStore: if the file states a schema version this library does not read.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._priors: dict[str, PriorParams] = {}
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        version = raw.get("schema_version", 0) if isinstance(raw, dict) else 0
        if version != PRIOR_STORE_SCHEMA_VERSION:
            raise UnreadablePriorStore(
                f"{self.path} is a version {version} prior store and this library reads "
                f"version {PRIOR_STORE_SCHEMA_VERSION}; delete it and refit, this store "
                f"rewriting only a file it could read"
            )
        for value in raw["priors"]:
            params = PriorParams.model_validate(value)
            self._priors[_key(params.entity_type, params.stat_id, params.scope)] = params

    def save(self, params: PriorParams) -> None:
        """Store `params` and rewrite the file, replacing any prior held for the same
        entity type, stat and scope.
        """
        self._priors[_key(params.entity_type, params.stat_id, params.scope)] = params
        self._write()

    def get(
        self, entity_type: str, stat_id: str, scope: dict[str, str]
    ) -> PriorParams | None:
        """Return the prior stored for exactly this entity type, stat and scope, or None."""
        return self._priors.get(_key(entity_type, stat_id, scope))

    def list_scopes(self, entity_type: str, stat_id: str) -> list[dict[str, str]]:
        """Return the scopes held for this entity type and stat, most dimensions first."""
        return _sorted_scopes([
            p.scope
            for p in self._priors.values()
            if p.stat_id == stat_id and p.entity_type == entity_type
        ])

    def _write(self) -> None:
        payload = {
            "schema_version": PRIOR_STORE_SCHEMA_VERSION,
            "priors": [params.model_dump() for params in self._priors.values()],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
