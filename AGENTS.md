# die-scouting — agent instructions

See [README.md](README.md) for what this project is and how the modules fit together.

## Docstring and comment style

**Describe the thing itself — its structure, its arguments and return, the rules governing its own fields. Not its role in a story about the system.**

These rules were derived from a rewrite exercise where the user rewrote every docstring in `die_scouting/`. The pattern was consistent, and it is not about length: the two docstrings kept nearly intact were among the longest, while several rejected ones were already short.

### 1. No em-dash asides that characterize rather than inform

Framing like "Pure wiring —", "Pure stats, no domain knowledge —", "Offline/periodic —" is editorial, not a fact about the callable.

### 2. No definition by negation

Don't say what something isn't, doesn't need, or doesn't know.

- Rejected: `Choose a prior distribution family by a stat-type heuristic, not an automatic goodness-of-fit search: ...`
- Kept: `Choose a prior distribution family by a stat-type heuristic: ...`

The entire heuristic and all three family mappings survived; only the clause saying what it *isn't* was deleted. Concrete detail is welcome, framing is not.

### 3. No claims about other parts of the system

"Everything downstream only ever sees Records", "everything statistical already happened upstream in `discretize`", "this is not part of the online per-roll pipeline". A reader of one function gains nothing from an assertion about another, and the claim rots when either changes.

Naming a real collaborator that appears in the signature or the return type is fine — `Output is intended to be persisted via a PriorStore` is grounded, `not part of the online per-roll pipeline` is narrative.

### 4. Use the code's own vocabulary, not invented metaphor

- Rejected: `The only domain/provider-aware seam. Everything downstream only ever sees Records.`
- User's version: `Protocol to adapt provider-specific data to a list of Records.`

"Protocol" and "Records" are in the signature; "seam" and "contract" were invented for the docstring.

### 5. Join clauses rather than stacking short sentences

The user's one edit to an otherwise-accepted docstring was a full stop changed to a semicolon, joining two related clauses. This mirrors their prose preference for connected sentences over fragments.

### Where the narrative content goes instead

Facts like "prior discovery runs offline, not per request" and "`n_faces` is caller-chosen, so a D6 or a D20 both work" are true and worth keeping. They belong in [README.md](README.md), which already describes how modules relate and where a stale claim is visible rather than buried in a docstring.

### One caution

Narrative framing can smuggle in claims the code doesn't support. `Record`'s original docstring said "one match's value for one stat" when `Record` has no match field — the phrasing came from design conversation, not from the type. Describing the actual fields would have caught it.

## Development

```
uv sync
uv run pytest
```
