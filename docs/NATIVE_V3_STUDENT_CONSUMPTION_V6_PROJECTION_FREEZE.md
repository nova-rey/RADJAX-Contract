# Native-v3 Student-consumption v6 projection freeze

This B2 record freezes the identity-bearing projections before any v6 schema
or digest implementation. It is additive: v1--v5 retain their existing field
interpretations byte-for-byte.

## `selected_passport_index/default`

The resource is a canonical JSONL sequence. Records are ordered strictly by
the zero-based `canonical_selection_index`; there is exactly one record for
each index in the contiguous range `0..N-1`. Each canonical record contains
exactly these authority fields, in canonical JSON key order:

1. `selected_example_id` (nonempty string)
2. `selected_position` (nonnegative integer)
3. `canonical_selection_index` (nonnegative integer)
4. `assigned_mode_id` (nonnegative integer)
5. `assignment_status` (the exact string `"selected"`)

The resource semantic identity frames each canonical record in sequence order;
the JSONL delimiter, whitespace, physical shard, source row, source position,
score, rank, score policy, selection policy, delivery path, timestamps, and
other provenance fields are excluded. Changing an included field changes both
this resource identity and the behavioral authority digest. Changing an
excluded field may change raw/package/composition identities, never behavioral
authority.

## `authority_reference/default`

The resource is one canonical JSON object with exactly these authority fields:

1. `schema_version` = `"radjax_v6_authority_reference_v1"`
2. `score_pass_authority_digest` (lowercase `sha256:` identity)
3. `selection_authority_digest` (lowercase `sha256:` identity of the fixed
   existing 25-field selection projection)
4. `language_binding_digest` (the resolved v5 canonical binding digest)
5. `behavioral_source_identity` (the v6 target/example source identity)

Keys are canonical JSON sorted keys. The existing fixed 25-field selection
projection itself is not recopied or reinterpreted by v6; its exact existing
digest is the sole selection projection input. Excluded fields include delivery
placement, source shard/row/position, producer commits, archive/tree hashes,
runtime configuration, dynamic selection thresholds or top-k limits, score
values, score policies, and all timestamps/paths. Excluded fields must be in a
separate non-authority receipt where their delivery provenance is required.

The authority-reference semantic identity and behavioral authority digest
change for every included-field change. Delivery-only changes cannot alter
either identity.

## Verified JSONL units

`example_registry/default` and `selected_passport_index/default` have only a
whole-resource raw identity in B2: their complete bytes are verified before
the first record is yielded. `selected_exemplar_payload/default` uses the
existing M7 shard/index logical record unit; a record may be yielded only after
its shard/index evidence and record parsing have succeeded. Completion of a
shard remains observable only at exhaustion. B2 makes no unsupported claim of
per-record cryptographic identity for ordinary JSONL resources.
