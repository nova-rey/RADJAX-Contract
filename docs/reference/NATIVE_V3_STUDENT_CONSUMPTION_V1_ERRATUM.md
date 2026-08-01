# Erratum: native-v3 Student Consumption v1 binding conflict

The released v1 declaration requires every Student resource to carry both an
`inventory_binding` and a `training_payload_binding`.  That latter binding
incorrectly implies that an independently derived Student sidecar must be a
member of the base native-v3 `training_payload` identity.  This conflicts with
the intended separation between the immutable native-v3 base semantic identity
and independently semantically-digested derived resources.

v1 remains an historical released contract for artifacts already produced and
validated under its terms.  It is not amended in place.  New producers MUST NOT
use v1 when declaring independently derived sidecars and MUST NOT invent,
backfill, or infer a `training_payload_binding` for those sidecars.  New
producers MUST use `native_v3_student_v2`, whose resource semantics are bound
by `(resource_id, role, instance_id, semantic_digest)` and whose physical
locator is raw-integrity-only.

This erratum does not change native-v3 base identity, revoke historical v1
artifacts, or claim a resolver/runtime implementation for v2.
