# Native-v3 Student Consumption Contract v3

## Status and negotiation

`native_v3_student_v3` is the current explicit profile for new native-v3
Student-consumption packages. It supersedes v2 for new production without
changing v2 validation or reinterpreting a v2 artifact. A caller selects the
profile at `validate_and_resolve_student_consumption`; a v3 request never
falls back to v2, and a v2 request never accepts a v3 declaration.

The base native-v3 `identity.semantic_digest` remains historical and unchanged.
V3 binds its independently derived resource semantics through a distinct v3
consumption identity. Physical locators, package profiles, transport wrapping,
and raw inventory digests remain delivery integrity rather than consumption
identity.

## Additional v3 evidence

In addition to the v2 target, registry, corridor, and exemplar resource
meaning, v3 requires the following closed JSON resource bodies:

- `row_range_declaration`: one positive example count and assignment count,
  ordered as `example_index_then_source_position`; both counts must match the
  resolved target and assignment resources.
- `delivery_receipt`: the declared Path A or Path B delivery value, NPZ
  assignment/statistics encodings, and stable native-v3 source roles. It does
  not use filesystem paths as semantic roles.
- `authority_reference`: an exact selection-integration hash matching the v3
  semantic identity plus at least one v1 or v2 score-pass authority hash.

All three bodies are raw-inventory verified, canonically semantically digested,
and then cross-checked by the portable resolver. A self-consistent refreshed
raw inventory cannot bypass a contradictory count, delivery, or authority
claim.

The authoritative schemas, recipes, vectors, rejection catalog, and fixture
catalog are packaged at
`contracts/radjax_tome/student_consumption/v3`. Contract supplies admission,
descriptor resolution, and verified-resource opening only; it remains neither
a Student loader nor a training/runtime policy.
