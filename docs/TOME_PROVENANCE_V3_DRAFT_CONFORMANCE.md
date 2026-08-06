# Tome provenance v3 draft conformance design

**Status:** unreleased Contract design companion to
`TOME_PROVENANCE_V3_DRAFT_SPEC.md`. It specifies future evidence, not a
validator, producer, consumer, fixture replacement, or changed historical path.

## Conformance matrix

The draft vector manifest is `docs/drafts/tome_provenance_v3_vectors.json`.
Independent implementations MUST reproduce all declared framed bytes and
digests. Its compact record maps exercise the framing grammar and are not claimed
to be complete production profile records. The future corpus starts from a valid minimal package; “before yield”
means the affected shard row is never exposed to a streaming consumer.

| Fixture class | Mutation / validation mode | Expected stage and result | Claim / nonclaim |
| --- | --- | --- | --- |
| Framing vectors | minimal record; several records; changed payload/order/authority/version/policy | Exact bytes/digests or unequal root at stages 6--7 | Byte-exact logical identity, not attribution |
| Null/empty/unknown | explicit null vs empty; absent required; unknown closed key | Distinct vector or reject stage 2/6 | No silent semantic extension |
| Nonsemantic packaging | whitespace/key presentation, recompression/member metadata, shard capacity, legal relocation | Same root, raw/archive identity may differ | Declared physical variance is nonsemantic |
| Stale content | probability/token/corridor/linkage change without refreshing proofs | Reject stage 3/5/7, before yield where shard affected | Accidental drift and stale evidence |
| Collection | delete/duplicate/omit/reorder; declared index tamper | Reject stage 5/7 | Complete ordered sequence |
| Raw shard | bit flip, truncate, append, replace, delete | Reject stage 3/4 before yield; localize member/shard | Raw integrity/localization |
| Graph/index | stale index, cover/header pointer, count/range mismatch | Reject stage 3/5 | Atomic cover/index/payload coherence |
| Binding | authority/Contract/profile/policy mismatch | Reject stage 6/7 or comparison | Governed semantic binding |
| Fully recomputed replacement | alter token and recompute all internal receipts | Standard accepts; original governed root rejects stage 8; original independent attestation rejects stage 9 | Correct self-attestation boundary, not honest-origin proof |
| Historical | v1--v6 declared artifacts/profiles | Original validator only, never converted to v3 | Historical contract preservation |
| Journal | partial shard/record, stale config, mixed run/authority, unreceipted, crash around promotion | Producer refuses or safely resumes before promotion | Transaction safety, not public consumer dependency |

The future corpus MUST cover directory and each supported archive transport,
one/many shards, capacity-one/capacity-many equivalent packages, externally
supplied attestation, and independent semantic reconstruction. It MUST retain
the fully recomputed mutation: standard acceptance and comparison/attestation
rejection are jointly required results.

## Experiment-to-contract mapping

| Experiment evidence | Proposed rule / surface | Required later evidence |
| --- | --- | --- |
| Ordered framed full records retained identity across resharding | FV3 sequence/root grammar, public semantic identity | Independent implementation/vector agreement |
| Authority/contract/policy bound root | Closed identity and governed binding | Published profile semantics |
| Raw shard receipt rejected corruption before rows yielded | One shard-index receipt/shard, validation stage 4 | Streaming implementation tests |
| Cover → header → inventory was acyclic | Public graph exclusions | Generated graph/cycle cases |
| Sealed receipts/ranges refused stale/incomplete transaction state | Private journal state machine | Producer crash/fault tests |
| Per-coordinate hashes and post-linkage reread/rehash/rewrite had no distinct final claim | Full-record frame plus sealed final-shard receipt | Retained-payload migration proof |
| `payload_sha256` and `payload_semantic_digest` were duplicate by construction | One semantic record frame; no duplicate per-record digest | Profile conformance |
| Row-repeated shard hash duplicated shard index | Shard index owns receipt once | Index/shard mapping tests |
| Fully recomputed token change was internally valid | Governed expected root/external record, not nested checksums | Independent expected-root custody |
| Synthetic benchmark reduced serialization/parsing/reread/rewrite/fs churn | Evidence only; no performance contract | Later real-path measurement after adoption |

The evidence source is Tome `audit/provenance-shape-bakeoff`
`d4402c2678a2adaa17b535f8674cf7dd59a77820`, based on
`b78821c6aec17335125df2e7f5823dce285735cf`, with Contract v0.8.0 pin
`b3275b8769c36b6261f4f241c47f0066c651e869`. Benchmark raw-evidence digest:
`sha256:fb2b4d6893b9381e396357e3fbe08bdd2d83592384358f01837360e6ca5fc503`;
full-suite digest:
`sha256:00a18cafb4e02fbd2cc90a742f446c000d7b6593ee17438efb8f877df22a3c85`.
The synthetic 256/2,048-record result demonstrates construction overhead at
tested synthetic scales only; it does not prove inference, accelerator,
end-to-end selected-pass, or unbounded-memory performance.

## Adoption decision gates

Implementation review must separately establish: completed Contract schemas and
validator; independent semantic-root agreement; vectors and full corpus;
historical compatibility; explicit Tome versioned path; Student without private
state; identical logical-payload migration; pre-yield shard rejection; journal
resume/fault proof; corrected threat-model mutations; governed and external
attestation fixtures; relevant full suites; unchanged historical artifacts; and
explicit default-transition review. It must also show one production correctness
path and a material retained-payload reduction before any M8 rebaseline. Failure
to detect a self-consistent replacement without a supplied external expectation
is not a standard-integrity failure.

## Precision-correction conformance cases

Every case begins from a fully valid v3 draft package unless stated otherwise;
all have stable identifiers, use the named validation mode, and prove only the
listed operational claim—not producer honesty, truthful teacher origin, or
validator integrity. `S` means standard validation, `G` adds external governed
input, `A` adds independently supplied external attestation.

| ID | Exact variation | Mode / expected stage-class | Mechanism and claim |
| --- | --- | --- | --- |
| PC01 | flip one shard byte | S / 4 `corrupt_shard`, before yield | shard receipt; raw localization |
| PC02 | truncate one shard | S / 4 `corrupt_shard`, before yield | size/digest; incomplete transfer |
| PC03 | append one shard byte | S / 4 `corrupt_shard`, before yield | exact raw receipt |
| PC04 | delete declared shard | S / 3 `missing_member` | inventory closure |
| PC05 | replace declared shard with another valid shard | S / 4 `corrupt_shard`, before yield | receipt binding |
| PC06 | add extra regular archive member | S / 1 `undeclared_member` | allowlist/inventory closure |
| PC07 | remove inventoried nonshard member | S / 3 `missing_member` | inventory closure |
| PC08 | duplicate one semantic record | S / 5 `index_incoherent` | contiguous unique sequence |
| PC09 | omit index row/record | S / 5 `index_incoherent` | count and coverage |
| PC10 | delete record but leave receipt | S / 4 `corrupt_shard`, before yield | raw receipt |
| PC11 | reorder records with stale indexes | S / 6 `semantic_sequence_mismatch` | ordered reconstruction |
| PC12 | stale shard raw receipt | S / 4 `corrupt_shard`, before yield | receipt verification |
| PC13 | stale payload-index row | S / 5 `index_incoherent` | location join |
| PC14 | stale shard-index row | S / 4 `corrupt_shard` or 5 `index_incoherent` | range/receipt join |
| PC15 | stale cover header reference | S / 3 `incoherent_package_graph` | cover/header binding |
| PC16 | stale header inventory reference | S / 3 `incoherent_package_graph` | header/inventory binding |
| PC17 | declared count mismatch | S / 5 `index_incoherent` | count agreement |
| PC18 | shard logical-range gap/overlap | S / 5 `index_incoherent` | contiguous ranges |
| PC19 | reference points to wrong path/schema | S / 3 `incoherent_package_graph` | closed reference |
| PC20 | duplicate key in JSON object | S / 2 `malformed_schema` | strict parser |
| PC21 | JSONL blank/CR/nonobject/missing final LF | S / 2 `malformed_jsonl` | strict JSONL bytes |
| PC22 | unsupported cover/version | S / 2 `unsupported_version` | exact dispatch |
| PC23 | profile/capability/header disagreement | S / 2 `incoherent_package_graph` | deterministic dispatch |
| PC24 | change authority source with stale identity | S / 7 `authority_mismatch` | authority derivation |
| PC25 | change contract version with stale identity | S / 7 `semantic_root_mismatch` | root binding |
| PC26 | change policy source with stale identity | S / 7 `policy_mismatch` | policy derivation |
| PC27 | change declared root | S / 7 `semantic_root_mismatch` | root recomputation |
| PC28 | capacity-one reshard with same records | S / pass, same root | physical layout excluded |
| PC29 | recompress/reorder members with same records | S / pass, same root | packaging excluded |
| PC30 | alter token and recompute all internal receipts/root | S / pass | honest self-contained boundary |
| PC31 | PC30 plus original governed input | G / 8 `governed_expected_root_mismatch` | immutable expected identity |
| PC32 | PC30 plus original external attestation | A / 9 `attestation_mismatch` | independent expected identity |
| PC33 | corrupt first streamed shard | S / no row yielded from shard | stage-4 prerequisite |
| PC34 | corrupt later streamed shard | S / earlier valid rows only; no row from corrupt shard | per-shard prerequisite |
| PC35 | stale journal configuration | producer / refuse resume | authority/config binding |
| PC36 | mixed-run receipts | producer / refuse resume | transaction identity/range |
| PC37 | cross-authority journal | producer / refuse resume | authority binding |
| PC38 | unreceipted staged shard | producer / refuse resume | seal receipt rule |
| PC39 | crash after each write, seal, range, complete, intent, rename, marker transition | producer / resume or nonconsumable as section 9 says | crash state machine |
| PC40 | incomplete promotion marker absent | producer / retry or reject, never public accept | promotion visibility |
| PC41 | v1 declared artifact | historical validator / native result | unchanged historical behavior |
| PC42 | v2 declared artifact | historical validator / native result | unchanged historical behavior |

Draft-vector cases `minimal_complete_record`, `several_ordered_records`,
`changed_record_order`, `changed_semantic_payload`, `changed_authority`,
`changed_contract_version`, `changed_behavioral_policy`,
`reshard_same_semantics`, `repackage_same_semantics`, and the nonroot unknown/
absent/empty cases provide the exact source inputs and expected preimages for
PC24--PC32. Numeric vectors additionally require signed minima/maxima, one
outside each bound, `-0`, `-0.0`, subnormal, overflow, and the three lexical
positive-one spellings; these are parser/conversion cases and do not introduce
an alternative root algorithm.
