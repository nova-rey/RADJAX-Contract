# Tome provenance v3 draft specification

**Status:** Contract-owned, unreleased design artifact for independent review.
It is not a released schema, validator, producer path, consumer API, or default.
The proposed successor is `radjax_tome_artifact_contract` **3.0.0-draft.1**. It
is parallel to the published v1/v2 Tome artifact-contract lineage, not a
Student-consumption v7 profile and not a change to `radjax-contract` 0.8.3.

Normative **MUST**, **MUST NOT**, **SHOULD**, and **MAY** have RFC 2119 meaning.
A later implementation is conformant only if it implements this specification,
its conformance companion, and the draft vectors. Historical v1--v6 validators
remain authoritative for their declared inputs. A v3 validator dispatches only
on the exact v3 wire schema and fails closed otherwise; it MUST NOT normalize an
older artifact into v3 and claim original-format validity.

Sections preceding **Precision correction 1** are retained only as review
history. Where they differ from that correction, they are nonnormative and the
correction is the sole draft contract.

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
 "contract_version":"radjax_tome_artifact_contract@3.0.0-draft.1",
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

## Precision correction 1 — normative supersession

This section supersedes every earlier conflicting or incomplete v3 draft rule.
The exact draft format version is now `3.0.0-draft.1`; its profile is
`selected_exemplar_semantic_profile_v3_draft`. The v2 asset at Contract tag
`v0.8.0` commit `b3275b8769c36b6261f4f241c47f0066c651e869`,
`src/radjax_contract/contracts/radjax_tome/v2/schemas/semantic_identity_v2.json`,
is migration context only: its authority, payload reference, and object dynamic
top-k shapes are open and are **not** incorporated normatively.

### Exact FV3-1 bytes

`FRAME(label,payload)` is exactly
`52 4a 54 46 45 31 00 || U16BE(len(label)) || label || U64BE(len(payload)) || payload`.
The magic is escaped `b"RJTFE1\\x00"`, hex `524a5446453100`, length 7; `\\x00`
means one NUL octet `00`, never four printable characters. `U16BE` and `U64BE`
are unsigned big-endian integers. `FV3-1` values are: null `00`; false `01`;
true `02`; signed integer `10 || I64BE`; finite binary64 `11 || IEEE754BE`;
text `20 || U64BE(length) || UTF8`; list `30 || U64BE(count) ||` length-prefixed
FV3 values; map `40 || U64BE(count) ||` ascending UTF-8-byte key followed by a
length-prefixed FV3 value. Keys are strict UTF-8 scalar text, unique, and sorted
unsigned-bytewise. Every map is closed by its named schema. No arbitrary nested
maps or parser-inferred numbers are legal.

| Domain | escaped bytes | hex | length |
| --- | --- | --- | ---: |
| logical record ID | `b"radjax.tome.v3.logical-record-id.v1"` | `7261646a61782e746f6d652e76332e6c6f676963616c2d7265636f72642d69642e7631` | 35 |
| authority identity | `b"radjax.tome.v3.semantic-authority.v1"` | `7261646a61782e746f6d652e76332e73656d616e7469632d617574686f726974792e7631` | 36 |
| policy identity | `b"radjax.tome.v3.behavioral-policy.v1"` | `7261646a61782e746f6d652e76332e6265686176696f72616c2d706f6c6963792e7631` | 35 |
| record sequence | `b"radjax.tome.v3.record-sequence.v1"` | `7261646a61782e746f6d652e76332e7265636f72642d73657175656e63652e7631` | 33 |
| semantic root | `b"radjax.tome.v3.semantic-root.v1"` | `7261646a61782e746f6d652e76332e73656d616e7469632d726f6f742e7631` | 31 |

`SHA256(FRAME(label,FV3(map)))` is emitted `sha256:` plus 64 lowercase hex.
Digest text is framed as text in a containing map; it is not decoded unless a
rule explicitly says raw digest bytes. Logical ID is that construction over
the closed map `{selected_example_id:text,selected_position:i64}`. Sequence
payload is `U64BE(N)` followed, for each actual `selection_index` in ascending
contiguous `0..N-1`, by `U64BE(index) || 32 raw digest bytes of logical ID ||
U64BE(len(FV3(record))) || FV3(record)`. Its hash is SHA-256 of the FRAME with
the record-sequence label. Root input is the exact identity map in the vector;
root is SHA-256 of its semantic-root FRAME.

Integers are exactly signed `[-2^63,2^63-1]`; JSON integer source accepts only
the JSON integer grammar (no plus, leading zero except `0`, decimal point, or
exponent), parses exactly, and rejects out of range. Source numeric lexical
form cannot choose a type: the field schema chooses i64 or binary64. For a
binary64 field, retain the JSON number lexeme, interpret it as an exact decimal
rational, then round IEEE-754 round-to-nearest ties-to-even to finite binary64;
frame its eight big-endian bytes. `1`, `1.0`, and `1e0` in an f64 field are the
same positive-one bytes; decimal/exponent forms in an i64 field reject. Negative
zero source rejects before framing. Nonnegative underflow rounds to positive zero
and is accepted; overflow, NaN, and infinities reject; subnormals are accepted.
Identity binds the normalized binary64 value, not spelling.

### Closed semantic schemas

All base record fields are required, non-null, and participate in FV3 unless
explicitly named ordering metadata. `selection_index` is a required u64 wire
field, is not in the record map, and is only sequence order. Text is nonempty;
integer fields below are nonnegative i64; f64 is finite as above.

| Fields | exact type and constraints |
| --- | --- |
| IDs/positions | `selected_example_id`, `source_score_policy`, `selected_policy`, `source_delivery_path`, `long_tail_class`, `semantic_tail_tag`, `selected_board`, `corridor_fingerprint_id`, `corridor_assignment_status`: text; `selected_position`, `source_shard_id`, `source_row`, `source_position`, `score_top_token_id`, `source_top_token_id`, `effective_top_k`, `sequence_length`, `vocab_size`, `num_buckets`, `dynamic_top_k_max`: nonnegative i64; `sequence_length`, `vocab_size`, `effective_top_k`, `dynamic_top_k_max` >= 1. |
| scores/masses | `selected_score`, `score_selected_position_entropy`, `source_score`, `teacher_entropy`: f64; `dynamic_mass_threshold`, `top_mass`, `tail_mass`, `effective_top_k_fraction_of_vocab`: f64 in [0,1]; `top_log_probs`: f64 list; `top_probs`, `bucket_masses`: f64 lists whose members are [0,1]. |
| token/list flags | `top_token_ids`: nonnegative i64 list; `top_selection_mask`: boolean list; `long_tail_warnings`: text list; `top_k_saturated`: boolean. The first three top lists and mask have length exactly `effective_top_k`; every token ID is `< vocab_size`; bucket masses length is `num_buckets`; `effective_top_k <= vocab_size`; selected/source positions are `< sequence_length`; source top token equals first token ID. |
| `payload_ref` | exact union by `kind`: `source_coordinate` has exactly `kind`, `source_shard_id`, `source_row`, `source_position`, all nonnegative i64. No other keys. |
| `dynamic_top_k` | exact union: `disabled_v1` has exactly `{kind:"disabled_v1"}`; `mass_threshold` has exactly `{kind:"mass_threshold",threshold:f64[0,1],max_k:i64>=1}`. For mass threshold, threshold/max_k equal `dynamic_mass_threshold`/`dynamic_top_k_max`; for disabled, both outer values are zero and `top_k_saturated` false. |
| corridor | `corridor_mode_id` is nonempty text (no integer variant); `corridor_fingerprint_id` nonempty text. |

Unknown or duplicate fields at every depth reject. Missing is never equivalent to
null or empty. No extension fields are allowed in draft. Future semantic
extensions require a new profile and domain/vector set. This self-contained
profile replaces v2 open objects; it does not silently import any experiment
harness convention.

Authority is a closed map with `schema_version`, `contract_version`,
`semantic_profile_id`, and sorted `entries`. Every entry has exactly `role`
(one of `teacher`, `tokenizer_vocabulary`, `corpus`, `score_pass`, `selection`,
`delivery`), `schema_id` (nonempty text), and `identity` (sha256 digest). All
six roles occur once, sorted by role UTF-8 bytes. Policy is closed with
`schema_version`, `contract_version`, `semantic_profile_id`, `selection_policy`,
`dynamic_top_k_policy`, and `corridor_link_policy`, all nonempty text. Authority
identity is `SHA256(FRAME(authority-label,FV3(authority-map)))`; policy identity
uses the policy label/map identically. Both maps bind version/profile and have
no null/unknown fields. Their framed preimages, digests, source maps, mutations,
and incorporation in the root are committed in the vector manifest.

### Closed public package contract

The only public regular members are fixed `cover_page.json`,
`manifests/content-manifest-header.json`,
`manifests/content-manifest-inventory.jsonl`,
`provenance/semantic-identity.json`, `provenance/semantic-authority.json`,
`provenance/behavioral-policy.json`, `provenance/capabilities.json`,
`selected_exemplars/layout.json`, `selected_exemplars/payload-index.jsonl`,
`selected_exemplars/payload-shards.jsonl`, and shard paths declared by receipt.
No optional public extensions exist in this draft. Every discovered regular file
must be fixed or appear exactly once in inventory; every inventory path must be
a discovered regular file. Extra, undeclared, missing, duplicate, symlink,
hardlink, device, FIFO, unsafe, or shadowing member rejects. Directories are
container metadata only and cannot shadow a regular member.

All object references are closed `{path:text,sha256:digest,size_bytes:i64>=0,
schema_version:text}`; an index reference additionally has `record_count:i64>=0`.
The machine-readable closed-field registry is
`docs/drafts/tome_provenance_v3_field_registry.json`; it is unreleased design
data and is authoritative for exact required-key/enum closure in this draft.
Cover contains exact cover/contract/profile versions, package `{profile_id,
transport}` (transport enum `directory|rtome|tgz`), capabilities reference,
identity/authority/policy references, header reference, and record/shard counts.
Capabilities are `{schema_version:"radjax_tome_capabilities_v1_draft",
required:[unique sorted text],optional:[unique sorted text]}`; required includes
`standard_integrity_v3_draft` and `streaming_shard_receipts_v3_draft`, unknown
required rejects, unknown optional is ignored only if it has no v3 effect.
Header contains its schema/contract/profile/capabilities, identity, layout, and
inventory references plus inventory `entry_count`. Layout is
`radjax_tome_payload_layout_v2_draft` with identity reference, both index
references, `record_count`, and nonsemantic `shard_capacity:i64>=1`. Shard rows
are exactly `{shard_id,path,sha256,size_bytes,first_selection_index,record_count}`;
payload rows exactly `{logical_record_id,selection_index,shard_id,row}`; ranges
are contiguous and cover `[0,N)`. Inventory rows are exactly `{path,sha256,
size_bytes,member_role,classification,required_for_standard_validation}` with
roles `semantic_identity|semantic_authority|behavioral_policy|capabilities|
payload_layout|payload_index|payload_shard_index|payload_shard`; classifications
`training_critical|integrity_or_provenance|diagnostic|human_readable|operational`.
False means raw receipt still required but semantic parsing not required.

Inventory excludes cover/header/inventory, so cover raw-receipts header; header
raw-receipts inventory; inventory raw-receipts every remaining member; layout
references indexes. This proves no directed raw-digest cycle. Strict JSON is
UTF-8 no BOM, one object root, no duplicate keys/nonfinite numbers/trailing
content. JSONL is UTF-8 no BOM, no CR/blank lines, each row object ends one LF,
and nonempty JSONL requires a final LF; a zero-count index is zero bytes only.
All cross-object version/profile/capability/reference/count values must agree;
cover selects dispatch, disagreement fails `incoherent_package_graph` before
semantic reconstruction. Archive receipt is external-only:
`{schema_version:"radjax_tome_archive_receipt_v1_draft",algorithm_id:"sha256",
archive_sha256,archive_size_bytes,transport,artifact_reference?}` and never a
member/root input. `artifact_reference`, when present, is the one canonical v3
artifact-reference value: nonempty strict UTF-8 text of at most 512 bytes, with
no NUL, CR, or LF. It is an issuer/caller release locator, not a package path or
semantic identity. It is optional, never null, excluded from all Tome semantic
identities, and raw-validated only as a receipt field. A receipt with it is
valid; malformed reference data fails `malformed_reference`, and each undeclared
sibling field fails `malformed_schema`.

### Closed comparison, attestation, and journal

Governed input is external, closed `radjax_tome_governed_comparison_v1_draft`:
schema version, expected root, expected authority identity, expected contract
version, expected profile ID, expected policy identity, and optional text
artifact reference. It is checked after standard root validation; mismatch is
`governed_expected_root_mismatch`. Attestation is external, closed
`radjax_tome_external_attestation_v1_draft`: the same five bindings, nonempty
artifact reference/issuer ID, RFC3339 UTC `issued_at`, nullable RFC3339 UTC
`expires_at`, `envelope_algorithm_id`, and base64 text `envelope`.
`artifact_reference` uses the canonical nonempty text definition above. This
draft supports exactly `envelope_algorithm_id:"fv3_raw_base64_v1"`: envelope is
RFC 4648 standard base64 using only `A-Z a-z 0-9 + /`, required canonical `=`
padding, no whitespace, and must round-trip as identical canonical base64 text.
Its decoded bytes MUST equal exactly `FV3(attestation_binding)`, not an opaque
cryptographic wrapper. `attestation_binding` is the closed map containing
`schema_version`, `semantic_root`, `semantic_authority_identity`,
`contract_version`, `semantic_profile_id`, `behavioral_policy_identity`,
`artifact_reference`, `issuer_id`, `issued_at`, `expires_at`, and
`envelope_algorithm_id`; `envelope` is deliberately excluded, so it cannot bind
itself. This raw fixture mode proves byte binding only; signing, signature
verification, keys, retrieval, and trust policy are deferred to future versioned
envelope algorithms. Malformed/noncanonical base64, decoded bytes unequal to
the required FV3 binding, and unsupported algorithms fail as
`attestation_envelope_invalid`, `attestation_binding_mismatch`, and
`attestation_algorithm_unsupported`. Optional/required availability and expiry
policy remains as stated; an attestation member inside the Tome is non-external
and cannot satisfy external-attestation mode.

Private journal governs local POSIX filesystem construction only. Write+fsync
staged shard; hash/size then fsync append sealed receipt; fsync contiguous-range
commit; fsync COMPLETE_INTENT; fsync PROMOTION_INTENT; atomically same-filesystem
`rename(no_replace)` staged public tree; fsync PROMOTED marker; then standard
public validation reports success. A crash before marker leaves no consumable
package and restart validates receipts/ranges then retries or removes staging.
If durable replace/fsync or atomic same-filesystem rename is unavailable, the
producer rejects that output transport. Journal state is never public/rooted.
