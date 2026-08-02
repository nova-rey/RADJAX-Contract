# Native-v3 Student-consumption v6 projection freeze

This B2 record freezes the identity-bearing projections before any v6 schema
or digest implementation. It is additive: v1--v5 retain their existing field
interpretations byte-for-byte.

## `selected_passport_index/default`

The resource is a canonical JSONL sequence. Records are ordered strictly by
`(rank, selected_example_id, selected_position)`, with ranks contiguous from
`1..N`. Each canonical record contains exactly these authority fields:

1. `selected_example_id`; 2. `selected_position`; 3. `rank`; 4.
`selected_score`; 5. `selected_policy`; 6. `corridor_mode_id`; 7.
`corridor_fingerprint_id`; 8. `corridor_assignment_status` = `"selected"`;
9. `selection_integration_config_hash`.

The resource semantic identity frames each canonical record in sequence order;
the JSONL delimiter, whitespace, physical shard, source row, source position,
delivery path, payload values, raw bindings, timestamps, wrappers, and
arbitrary extensions are excluded. Changing an included field changes both
this resource identity and the behavioral authority digest. Changing an
excluded field may change raw/package/composition identities, never behavioral
authority.

## `authority_reference/default`

The resource is one canonical JSON object with exactly these authority fields:

1. `schema_version` = `"radjax_behavioral_authority_reference_v6"`
2. `selection_integration_config_hash` (lowercase `sha256:` identity)
3. `score_pass_authority_hash` (lowercase `sha256:` identity)
4. `delivery_authority_hash` (lowercase `sha256:` identity)

Keys are canonical JSON sorted keys. The historical
`score_pass_authority_hash_v1` alias, derived passport/resource digests, raw
bindings, transport, time, and arbitrary extensions are excluded. The fixed
existing selection projection is not recopied or reinterpreted; its evidenced
selection-integration hash is the sole selection input. Delivery placement,
source coordinates, producer commits, archive/tree hashes, runtime config,
dynamic thresholds/top-k limits, scores, policies, and timestamps remain
non-authority receipt data.

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
