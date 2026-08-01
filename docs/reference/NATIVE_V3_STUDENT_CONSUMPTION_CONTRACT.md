# Native-v3 Student Consumption Contract

## Status and scope

This is the released normative record for `native_v3_student_v1`. It describes a
portable producer/consumer boundary for native-v3 Tome material.  It does not
implement a Student reader, batching policy, objective, JAX materializer,
training schedule, or v4 Student profile.

Legacy `radjax_tome_cover_v3` artifacts remain valid under their historical
admission contract.  They are not Student-consumable unless they carry the
closed `radjax_tome_cover_v3_student_consumption_v1` extension and its
`manifests/student_consumption_v1.json` declaration.

## Identity and physical delivery

The existing native-v3 semantic root remains the base artifact identity.  The
consumption declaration adds a distinct
`radjax_tome_student_consumption_semantic_identity_v1` digest.  The latter is
the identity of resolved Student batch meaning.  It hashes the profile,
vocabulary and sequence contract, role/instance records, semantic resource
digests, joins, target declarations, and selection authority.  It excludes
physical paths, package profile, transport, raw inventory digests, and Path A
or Path B delivery provenance.

The declaration is raw-integrity-bound through the ordinary content manifest.
It does not hash itself.  A logical resource has one inventory member and one
native-v3 `training_payload.logical_id` binding, but an NPZ resource may have
many named array members.  Roles and instances are the semantic authority;
paths are delivery locators only.

The canonical `native_v3_student_consumption_v1` vector declares packed
`corridor_assignment` as an `npz` resource. Its
`training_payload_binding` and `inventory_binding` are explicit, equal
inventory-backed delivery locators; neither field is inferred from a role or a
path convention. Legacy JSON corridor-assignment representations are
historical/adversarial inputs and fail with the deterministic container/encoding
rejection; they are not an alternative canonical representation for this
profile.

The consumption manifest and consumption semantic identity contain the same
ordered tuple for every resource: `(resource_id, role, instance_id,
semantic_digest)`.  `resource_id` and `(role, instance_id)` are each unique;
the manifest adds exactly one training-payload binding and exactly one inventory
member binding.  The portable validator recomputes this projection before
accepting the consumption digest.  The cover's
`student_consumption.manifest_sha256` MUST equal the `sha256` of its single
`manifests/student_consumption_v1.json` inventory entry.  This is a raw
integrity relation, not a second semantic digest.

Adding the declaration changes the content-manifest, cover, directory/tree,
and archive raw digests.  It does not reinterpret or rewrite an existing v3
semantic root.  A relocation can change a path-bound legacy identity while
preserving consumption identity when role-instance content is unchanged.

## Teacher-logit-position alignment

An assignment coordinate `p` refers to `output.logits[:, p, :]` and to the
same Student logit position.  A consumer MUST NOT shift it.  In a causal LM,
that logit is ordinarily the distribution for the continuation after consuming
`input_ids[p]` (conceptually token `p + 1`).  The final valid position remains
because its teacher continuation distribution is still a behavior target even
though the continuation token is not present in the input row.

## Required roles

The `native_v3_student_v1` profile requires both corridor and exemplar
surfaces.  Required Student-batch resources are target-shard `input_ids`,
`attention_mask`, and `corridor_lengths`; the example registry; mode table;
packed assignment coordinates, mode IDs, and weights; selected-passport index;
and selected exemplar payloads.

Required validation-only resources are the five observed corridor statistics
(`entropy`, `top1_margin`, `top8_mass`, `top32_mass`, `tail_mass`), row-range
declarations, delivery receipt, and cover authority references.  Contract
proves every unmasked coordinate occurs exactly once and its observed statistics
fall in the selected mode's finite inclusive bounds.  These resources are not
Student loss inputs.

Fingerprints, fingerprint indices, confidence, score arrays, human reports,
and debug provenance are optional diagnostics.  Path A
(`one_pass_pruned_candidate`) and Path B (`two_pass_rerun_selected`) are
required provenance facts when an artifact claims them, but never change batch
meaning or the consumption digest.

## Arrays, joins, and numeric rules

Target-shard rows are ordered contiguous global example ranges.  `input_ids`
and `attention_mask` are `int32[example, token_position]`; token IDs satisfy
`0 <= id < vocab_size`; a mask is a one-prefix followed by zeros; and
`corridor_lengths:int32[example]` equals its mask sum.  Assignment rows sort
strictly by `(global_example_index, position)`, cover each unmasked coordinate
exactly once, refer to one unique artifact-local mode ID, and have finite
nonnegative weights.  Zero weights are valid assignments.

Modes expose unique IDs and the ordered tracked statistics `entropy`,
`top1_margin`, `top8_mass`, `top32_mass`, and `tail_mass`.  Every bound is
finite and inclusive.

The exemplar passport key is `(selected_example_id, selected_position)` and is
unique.  A canonical passport digest additionally binds selected board,
selected policy, and fixed selection-authority identity.  Exemplar ranks are
exactly `1..N`; each joins a target row, an unmasked logit position, and a
corridor assignment.

Dynamic top-k slots share a declared width.  The selection mask is a true
prefix with `effective_top_k` entries.  Active IDs are unique and in the
vocabulary; active probabilities are positive and descending.  Inactive slots
are exactly ID `0`, probability `0.0`, and log probability `-100.0`.
`top_mass` is the ascending-slot sum of active probabilities, `tail_mass` is
`1 - top_mass`, and finite nonnegative bucket masses sum to tail mass.

Contract v1 constants are: probability/mass `atol=1e-6`, `rtol=1e-5`; log
probability `atol=1e-5`, `rtol=1e-5`; summation uses ascending slot order and
IEEE-754 binary64 accumulation.  Finite positive subnormal active probabilities
are accepted.  NaN and infinity fail.  Negative zero normalizes to positive
zero where zero is legal.

## Canonical payloads and delivery

Canonical JSON and JSONL are UTF-8, reject duplicate object keys and nonfinite
numbers, and use compact sorted JSON for semantic objects.  JSONL uses one
object per LF-terminated line.  NPZ semantic hashing is a framed sequence sorted
by member name: UTF-8 member name, dtype, rank, dimensions, axes, and canonical
little-endian C-order bytes.  Raw inventory hashes still bind the original file.

Resolved-resource opening is context-managed and verifies safe normalized
members.  Before opening hostile archives it enforces: at most 100,000 members,
at most 64 GiB per member, at most 1 TiB uncompressed total, and at most a
10,000:1 compression ratio.  Traversal, duplicate members, links, and special
files fail.

`strict=True` requires canonical transport and no noncanonical warning.
`strict=False` may report a documented safe noncanonical transport warning, but
never relaxes safety, integrity, semantic, profile, or version validation.

## Deterministic issues

Issues run in fixed phases: profile/cover, archive safety, inventory/integrity,
bindings, resource encoding, structural joins, corridor, exemplar, provenance,
then semantic digest.  Dependent checks are suppressed after a prerequisite
fails; independent issues accumulate and sort by `(phase, resource_id, code)`.
Each issue includes `code`, `phase`, `profile_id`, and applicable resource,
instance, locator, expected, and observed context.  Conformance fixtures define
both a primary issue and the complete expected issue tuple.

## Nonclaims

This contract resolves validated semantic resources and verified byte streams.
It does not create Student batches, choose loss functions, infer an objective,
allocate devices, execute JAX, train a model, or alter M7/v4 streaming behavior.
