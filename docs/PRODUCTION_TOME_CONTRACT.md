# Production Tome Contract

P1.5 adds an additive consumer contract for RADJAX-Tome production cover-page
version 2. Legacy v0 Tome models and validators remain separate and are not
silently reinterpreted.

## Public API

```python
from radjax_contract.tome import (
    inspect_production_tome,
    load_production_tome,
    validate_production_tome,
)
```

`validate_production_tome()` validates the indexed artifact bytes and the typed
corridor and exemplar semantics. `load_production_tome()` returns the same
validation result with parsed projections when available.
`inspect_production_tome()` additionally compares the pass plan's capability
requirements with an explicit consumer capability set.

Inspection distinguishes structural validity from consumability. Unknown role
strings, surface kinds, target scopes, and optional metadata are preserved.
Unknown required capabilities or roles can block consumption without making the
cover page unparsable.

## Validation Boundary

The production validator reads `cover_page.json` and resolves every other file
through its indexed semantic role. It does not walk the artifact directory or
guess producer filenames.

The validator checks:

- identity, layout, content path safety, role cardinality, hashes, and sizes;
- producer validation status and the indexed validation report;
- surface IDs, capability declarations, prerequisites, and pass ordering;
- stat-band corridor modes and packed assignment arrays;
- selected exemplar index/payload joins, dynamic top-k, masks, mass accounting,
  token domains, and corridor mode linkage.

Producer validation and Contract validation remain separate facts. Passing one
does not imply that the other was skipped.

## Canonical Fixture

The deterministic fixture is package data at
`radjax_contract/testing/fixtures/production_multi_surface_v1/`. Tests and
downstream consumers should obtain it through:

```python
from radjax_contract.testing import production_tome_fixture_path
```

The fixture uses eight synthetic examples, two stat-band corridor modes, packed
NumPy assignments, diagnostic fingerprint lineage, four selected exemplars with
effective top-k values 2 through 5, and the checkpointed corridor-to-exemplar
pass plan. It requires no network or ML runtime dependencies.

The normative producer semantics are versioned in
[`reference/RADJAX_TOME_STUDENT_CONSUMER_HANDOFF.md`](reference/RADJAX_TOME_STUDENT_CONSUMER_HANDOFF.md).
