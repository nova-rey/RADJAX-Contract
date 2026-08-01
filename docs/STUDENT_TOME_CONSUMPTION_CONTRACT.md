# Native Tome v3 Student-consumption contract

Contract publication `1.0.0` defines the portable `native_v3_student_v1`
profile. It is the shared authority for turning a validated Tome v3 directory
into architecture-neutral corridor and exemplar batches. Student must not read
Tome source modules, private paths, or inferred array layouts.

The normative assets are packaged under
`radjax_contract/contracts/radjax_tome/consumption/v1`. The profile maps stable
`identity.training_payload[].logical_id` roles to content-manifest inventory,
including indexed target and selected-exemplar shard families. It declares
required/optional payloads, encodings, exact dtypes/ranks/axes, token and mask
alignment, corridor assignment/bounds, exemplar passport/target semantics,
delivery provenance, canonicalization, and deterministic rejection codes.

The public gate is:

```python
from radjax_contract.tome import validate_student_tome_consumption

report = validate_student_tome_consumption(tome_directory)
if not report.ok:
    raise ValueError(report.errors)
```

`one_pass_pruned_candidate` (Path A) and `two_pass_rerun_selected` (Path B)
are accepted provenance authorities. They are never target or loss authority.
Identical selected-example passports and payload values have identical Student
meaning regardless of delivery path.

The packaged `native_v3_student_v1` fixture is producer-generated and its
semantic digest is
`sha256:c7eb093e3481504197018209e94eca41a5b31efc16588d54cc6b453ac1e91d72`.
