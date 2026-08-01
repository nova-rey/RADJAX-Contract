# Supersession: native-v3 Student Consumption v2

`native_v3_student_v2` remains a released historical contract and is not
modified. It is superseded for new native-v3 Student-consumption production by
`native_v3_student_v3`.

v3 preserves v2's separation of the immutable native-v3 base semantic identity
from independently semantically-digested sidecars. It adds normative semantic
declarations for `row_range_declaration`, `delivery_receipt`, and
`authority_reference`, including the closed receipt and authority-reference
bodies defined in the v3 asset recipes. These declarations make the consumption
of row range, delivery path, and selection/score authority explicit rather
than producer-private inference.

Profile negotiation is exact: an artifact declared as
`native_v3_student_v3` MUST be resolved as that profile. A v3 consumer MUST
NOT fall back to `native_v3_student_v2`, and a v2 resolver MUST NOT accept a
v3 artifact by stripping or ignoring its declarations. The same rule applies
to profile identifiers presented at the public resolution boundary.

This supersession does not amend v2, revoke historical v2 artifacts, rewrite
the native-v3 base identity, or specify a Student loader, batching policy,
objective, or runtime.
