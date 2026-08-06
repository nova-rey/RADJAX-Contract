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
