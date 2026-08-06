# Tome provenance v3 draft specification

**Status:** Contract-owned, unreleased design artifact for independent review.
It is not a released schema, validator, producer path, consumer API, or default.
The proposed successor is `radjax_tome_artifact_contract` **3.0.0-draft**. It
is parallel to the published v1/v2 Tome artifact-contract lineage, not a
Student-consumption v7 profile and not a change to `radjax-contract` 0.8.3.

Normative **MUST**, **MUST NOT**, **SHOULD**, and **MAY** have RFC 2119 meaning.
A later implementation is conformant only if it implements this specification,
its conformance companion, and the draft vectors. Historical v1--v6 validators
remain authoritative for their declared inputs. A v3 validator dispatches only
on the exact v3 wire schema and fails closed otherwise; it MUST NOT normalize an
older artifact into v3 and claim original-format validity.

## Assurance layers and nonclaims

| Layer | Required input | Claim | Nonclaim |
| --- | --- | --- | --- |
| Standard operational validation | Tome + this contract | The declared package is coherent, intact, safely streamable, and bound to declared governed authority. | It cannot detect a fully recomputed self-consistent replacement without externally supplied expected identity. |
| Governed semantic comparison | Valid Tome + immutable Golden/Contract expected identity outside it | A valid result equals approved behavioral identity. | It does not establish honest production or trustworthiness of expected evidence. |
| External attestation | Valid Tome + expected record from a distinct trust domain | Artifact equals published/attested identity. | It does not prove truthful model origin, signer/key/validator safety, or independence where producer and attester share control. |

No internal checksum proves honest producer source, uncompromised validator,
truthful teacher origin, or resistance to an attacker controlling both artifact
and expected evidence. Those claims require independent reproduction, trusted
execution, separate review/publication, or another truly independent authority.

## Version and public proof surface

Draft wire identifiers are `radjax_tome_cover_v5_draft`,
`tome_content_manifest_header_v4_draft`,
`tome_content_manifest_inventory_v4_draft`,
`radjax_tome_semantic_identity_v3_draft`,
`radjax_tome_payload_index_v3_draft`,
`radjax_tome_payload_shard_index_v2_draft`, and
`selected_exemplar_semantic_profile_v3_draft`. The exact `draft` suffix is
mandatory until a reviewed release gives a new immutable identifier. A consumer
selects it only when cover and capability declaration are exact; unsupported
versions fail `unsupported_version` before dependent interpretation. No current
capability/API change is implied.

Structured public members are UTF-8 JSON or LF-terminated JSONL. Parsing MUST
reject invalid UTF-8, duplicate JSON keys, non-finite numbers, trailing content,
and malformed closed cores. Member paths are nonempty relative POSIX ASCII paths
using `[A-Za-z0-9._/-]`, with no leading slash/backslash, empty/`.`/`..` segment,
or duplicates. `sha256:<64 lowercase hex>` is SHA-256 of exact member bytes;
`size_bytes` is exact octets. JSON presentation matters only to raw integrity
unless section 4 frames it semantically.

```text
cover_page.json --raw receipt--> manifests/content-manifest-header.json
header --raw receipt--> manifests/content-manifest-inventory.jsonl
inventory --raw receipts--> semantic identity, layout/indexes, shards, all other members
```

The inventory lists every public member exactly once except itself, header, and
cover. It MUST list none of those three. A separately delivered outer archive
receipt MAY hash transport bytes but MUST NOT appear inside those bytes.

| Object / required fields | Producer and validator responsibility | Identity / evolution |
| --- | --- | --- |
| Cover: `schema_version`, `package.profile_id`, `semantic_identity_ref`, `manifest_header_ref`, `declared_authority_ref`, `behavioral_policy_ref`, `record_count`, `shard_count` | Sole public entry point; verify header receipt before trusting locations; all values agree with identity/indexes. | Semantic bindings enter identity; header receipt is raw. Closed core. |
| Identity: `schema_version`, `contract_version`, `semantic_profile_id`, `semantic_authority_identity`, `behavioral_policy_identity`, `record_count`, `ordered_record_sequence_digest`, `semantic_root` | Derive/recompute only by section 4 after ordered reconstruction. | All except stored root are semantic. Closed core. |
| Layout: `schema_version`, `semantic_identity_ref`, `payload_index_ref`, `shard_index_ref`, `record_count` | Owns exactly one each index reference; all agree. | Graph/coherence, not an additional semantic identity. |
| Payload-index row: `logical_record_id`, `selection_index`, `shard_id`, `row` | One unique logical-to-physical location; indexes contiguous from zero and agree with parsed rows. No shard digest is copied here. | ID/order semantic checks; location is physical. |
| Shard-index row: `shard_id`, `path`, `sha256`, `size_bytes`, `first_selection_index`, `record_count` | One final sealed receipt/shard; ranges unique, contiguous, complete. Verify raw bytes before parse or stream yield. | Raw integrity and logical coverage; path/raw receipt excluded from root. |
| Inventory row: `path`, `sha256`, `size_bytes`, `classification`, `required_for_standard_validation` | One raw receipt for each eligible public member; reject missing/extra/duplicate/mismatch. | Raw integrity/localization only. |

The profile-owned closed semantic authority object MUST include governed teacher,
tokenizer, vocabulary, corpus, selector, configuration, and behavioral authority
used to make records. Its digest and the closed behavioral-policy-object digest
use section 4 with identifier-specific labels. Both forbid runtime timestamps,
hosts, temporary paths, compression, shard capacity, and private journal fields.
Unknown authority/policy/record fields fail closed; future semantics need a new
profile identifier. V3 deliberately removes native per-coordinate `payload_hash`,
post-linkage reread/rehash/rewrite, duplicate record digest, repeated row shard
digest, and nested self-attestation. Their operational claims map to full record
framing, final sealed shard receipts, indexes, or an explicit external boundary.

## Byte-exact semantic framing and root

This grammar is normative and independent of archive ordering, shard boundaries,
compression metadata, filesystem timestamps/absolute paths, temporary names, and
private producer state. `U64(n)` is eight big-endian octets, `0 <= n < 2^64`.
`LP(b) = U64(len(b)) || b`. Labels below are exact ASCII bytes including `00`.
Text is strict UTF-8 Unicode scalar values with no normalization; null and empty
text are distinct.

`FV3(value)` is tag plus bytes:

| Tag | Value | Following bytes |
| ---: | --- | --- |
| `00` | null | none |
| `01` / `02` | false / true | none |
| `10` | integer | sign `00` nonnegative / `01` negative then `U64(magnitude)`; negative zero forbidden |
| `11` | number | finite IEEE-754 binary64, big-endian; NaN, infinity, and `-0.0` forbidden |
| `20` | text | `LP(strict_utf8)` |
| `30` | list | `U64(count)` then `LP(FV3(item))` in supplied order |
| `40` | map | `U64(count)` then `LP(utf8_key)||LP(FV3(value))`, keys strictly increasing unsigned UTF-8 bytes |

Maps have text keys only; duplicate keys fail before framing. JSON source parsing
MUST retain number lexemes: integral fields parse exactly to the permitted signed
integer domain; binary64 fields convert the exact decimal rational lexeme using
IEEE-754 round-to-nearest, ties-to-even. A nonintegral lexical number in an
integer field fails. Thus host JSON float rendering cannot choose bytes.
`H(label, values...) = SHA256(label || LP(FV3(value_1)) || ...)`, emitted as
`sha256:` plus lowercase hex. Labels are not length-prefixed values.

The proposed closed profile record map contains these exact semantic fields:
`selected_example_id`, `selected_position`, `selected_score`,
`score_selected_position_entropy`, `score_top_token_id`, `source_shard_id`,
`source_row`, `source_position`, `source_score`, `source_top_token_id`,
`source_score_policy`, `payload_ref`, `selected_policy`, `source_delivery_path`,
`top_token_ids`, `top_log_probs`, `top_probs`, `top_selection_mask`,
`effective_top_k`, `top_mass`, `tail_mass`, `bucket_masses`, `teacher_entropy`,
`sequence_length`, `vocab_size`, `num_buckets`, `dynamic_top_k`,
`dynamic_mass_threshold`, `dynamic_top_k_max`, `top_k_saturated`,
`long_tail_class`, `long_tail_warnings`, `effective_top_k_fraction_of_vocab`,
`semantic_tail_tag`, `selected_board`, `corridor_mode_id`,
`corridor_fingerprint_id`, `corridor_assignment_status`. The later released
profile schema MUST assign each scalar/list type and cross-field rule. For the
presently open `payload_ref` and object-form `dynamic_top_k`, their entire
recursively valid FV3 map is semantic and included verbatim: no nested key is
silently ignored. Null is rejected wherever the v2 semantic record forbids it.
Wrapper/address/raw/transport/runtime fields are excluded. `selection_index` is
ordering metadata.

The draft freezes scalar framing now: integer fields are `selected_position`,
`score_top_token_id`, `source_shard_id`, `source_row`, `source_position`,
`source_top_token_id`, `effective_top_k`, `sequence_length`, `vocab_size`,
`num_buckets`, and `dynamic_top_k_max`; binary64 fields are `selected_score`,
`score_selected_position_entropy`, `source_score`, `top_mass`, `tail_mass`,
`teacher_entropy`, `dynamic_mass_threshold`, and
`effective_top_k_fraction_of_vocab`; boolean fields are `top_k_saturated` and
the members of `top_selection_mask`; text fields are `selected_example_id`,
`source_score_policy`, `selected_policy`, `source_delivery_path`,
`long_tail_class`, `semantic_tail_tag`, `selected_board`,
`corridor_assignment_status`, and members of `long_tail_warnings`; integer-list
fields are `top_token_ids`; binary64-list fields are `top_log_probs`,
`top_probs`, and `bucket_masses`; and `corridor_mode_id` and
`corridor_fingerprint_id` are either text or integer. `payload_ref` is a
nonempty FV3 map, and `dynamic_top_k` is a boolean or nonempty FV3 map. Existing
v2 field-presence and cross-field semantic constraints remain mandatory until a
future released v3 profile supersedes them explicitly.

For projection `r`, `logical_record_id(r) = H(b"radjax-tome-logical-record-id-v1\\x00", {"selected_example_id": r.selected_example_id, "selected_position": r.selected_position})`.
It is required, recomputed, unique, and stable across packaging.

Records sort only by validated `selection_index == 0..N-1`. Let `SEQ` be
`b"radjax-tome-semantic-sequence-v3\\x00" || U64(N) ||` each
`LP(FV3(closed_record(r)))` in order. `ordered_record_sequence_digest = SHA256(SEQ)`.
The identity map excluding `semantic_root` is exactly:

```text
{"schema_version":"radjax_tome_semantic_identity_v3_draft",
 "contract_version":"radjax_tome_artifact_contract@3.0.0-draft",
 "semantic_profile_id":..., "semantic_authority_identity":...,
 "behavioral_policy_identity":..., "record_count":N,
 "ordered_record_sequence_digest":"sha256:..."}
```

`semantic_root = H(b"radjax-tome-semantic-root-v3\\x00", identity_without_root)`.
Changing authority, policy, Contract version, profile, record value/order/count
changes the root; resharding/repacking does not. Normative pseudocode is:

```text
assert selection_indexes == [0..N-1]
assert each declared logical_record_id == logical_record_id(record)
seq = SEQ_LABEL || U64(N) || concat(LP(FV3(project(record))) for ordered records)
assert declared_sequence == sha256(seq)
assert declared_root == H(ROOT_LABEL, closed_identity_without_root)
```

## Private construction journal

`radjax_tome_construction_journal_v1_draft` is private producer state: never
packaged, inventoried, rooted, archived, or required by Student/ordinary
consumers. Required closed fields are `transaction_id`, `configuration_identity`,
`semantic_authority_identity`, `state`, `sealed_shards`,
`committed_next_selection_index`, `completion_intent`, `promotion_marker`.
Each append-only sealed receipt records shard ID, private/final logical member
name, raw digest, size, first selection index, and count.

```text
OPEN -> SEALING -> OPEN                 (durable shard then durable receipt)
OPEN -> COMPLETE_INTENT                 (all sealed ranges contiguous)
COMPLETE_INTENT -> PROMOTING -> PROMOTED (atomic promotion marker)
PROMOTING -> COMPLETE_INTENT             (restart sees incomplete promotion)
OPEN/SEALING/COMPLETE_INTENT/PROMOTING -> ABORTED
```

Only OPEN accepts records. A shard becomes sealed only after durable final bytes,
size/digest, and durable receipt. Restart refuses changed authority/configuration,
missing/mismatched receipt members, unreceipted/overlapping/noncontiguous ranges,
or a next index not equal to sealed range end. COMPLETE_INTENT derives public
evidence only from sealed receipts. PROMOTING without marker is nonconsumable
until retry/rollback; PROMOTED requires atomic marker and public standard
validation. Required atomicity is durable shard-before-receipt, durable record/
marker replace-or-create, and atomic final promotion/equivalent visible marker.

## Validation, governed comparison, and attestation

Validation stages are deterministic and dependent stages stop after prerequisite
failure: (1) safe container/member discovery; (2) exact schema/profile dispatch;
(3) cover/header/inventory raw graph; (4) raw shard size/digest **before parsing
or yielding any row**; (5) index/range/count/pointer coherence; (6) profile,
logical-ID, ordered semantic reconstruction; (7) sequence/root verification;
(8) optional governed expected-root comparison; (9) optional external attestation
comparison. Classes distinguish unsupported version, malformed schema, corrupt
member/shard, incomplete container, incoherent graph, semantic-root/authority/
policy mismatch, governed mismatch, unavailable-required attestation, attestation
mismatch, and producer-invalid private state.

Governed input is a closed external object containing expected root, authority
digest, contract version, profile ID, and policy digest. All five must equal a
standard-valid artifact. Golden/Contract qualification retains it outside the
tested Tome. Therefore a fully recomputed altered Tome passes standard mode with
no expected identity yet fails governed mode against the original expected root.

External record `radjax_tome_external_attestation_v1_draft` has `semantic_root`,
`semantic_authority_identity`, `contract_version`, `semantic_profile_id`,
`behavioral_policy_identity`, `artifact_reference`, `issuer_id`, `issued_at`,
`expires_at` (RFC3339 UTC/null), and `envelope {algorithm_id,payload}`. It is
outside the Tome or delivered by an independently trusted channel. Envelope is
only a future signed-digest/transparency/authority-record extension point: this
draft implements no signing, keys, verification library, network, service,
issuer policy, or clock policy. Optional consumers may ignore it; required policy
fails unavailable; supplied mismatching bindings fail. An inside-only receipt is
not external attestation.

## Later adoption gates

Before separate adoption: released schemas/validator; independent root/vector
agreement; full conformance corpus; unchanged v1--v6 proof; explicit Tome v3
path; Student without journal; identical-retained-payload migration; pre-yield
stream corruption proof; journal fault/resume proof; corrected threat-model
mutations; governed/attestation fixtures; full suites; unchanged historical
artifacts; explicit review/default decision. Only then may M8 rebaseline after
format adoption; it is a separate performance gate.
