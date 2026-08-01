# Native-v3 Student Consumption Contract v2

## Status and scope

`native_v3_student_v2` is the normative additive Student-consumption profile
for a native-v3 Tome base artifact and independently semantically-digested,
derived sidecar resources.  The base artifact retains its existing native-v3
`identity.semantic_digest`; v2 neither rewrites nor reinterprets that identity.
The separate `radjax_tome_cover_v3_student_consumption_v2` schema is an
extension declaration, not a replacement for the base-cover schema.

## Identity and derived resources

The v2 manifest MUST declare `base_artifact_semantic_digest`, a v2
`semantic_identity`, and resources containing exactly `resource_id`, `role`,
`instance_id`, `semantic_digest`, `inventory_binding`, `encoding`,
`classification`, and `consumption`.  Each resource is a derived sidecar with
its own semantic digest.  It MUST NOT declare or require the legacy v1
`training_payload_binding` field.

The semantic identity hashes the ordered tuple `(resource_id, role,
instance_id, semantic_digest)` for each resource, together with the declared
vocabulary, sequence, joins, and selection authority.  `resource_id` and the
pair `(role, instance_id)` are each unique.  A resource's `inventory_binding`
is a raw-delivery locator only.  It, manifest and archive paths, package
transport, and raw inventory digests are excluded from consumption identity.
Consequently identical derived semantics retain consumption identity after
relocation or repackaging; raw inventory validation remains mandatory for the
delivered bytes.

## Canonical digests

JSON/JSONL semantic records and NPZ sidecars use the v2 canonical recipes in
the contract asset tree.  JSON identity hashing omits the self-referential
`semantic_digest` member.  NPZ hashing frames the ordered member semantics,
not the container filename or ZIP layout.  These are independent semantic
digests: no native-v3 training-payload logical ID is a required join for a v2
derived resource.

## Nonclaims

Contract supplies portable admission and resolution through
`validate_and_resolve_student_consumption(..., profile_id="native_v3_student_v2")`
and verified-resource opening through `open_verified_student_resource`.  It
does not implement a Student loader, batching policy, objective, or training
runtime.
