# RADJAX-Contract Bible

This file is append-only institutional memory for shared Contract decisions.

## 2026-07-10 - P1.5 production Tome alignment begins

- Froze the Student consumer handoff in Contract because Contract is the
  neutral semantic boundary shared by the Tome producer and Student consumer.
- Production Tome requires an additive versioned schema; legacy v0 artifacts
  must remain unambiguous rather than being silently reinterpreted.
- Unknown roles and surfaces must remain inspectable so future artifacts can be
  parsed and rejected by capability instead of crashing during parsing.
- Corridor mode IDs are training identifiers while fingerprint IDs are
  diagnostic lineage; the Contract must represent them as distinct types.
- Multi-surface capability sets replace the provisional one-adapter inspection
  model so new behavioral surfaces do not require another schema reset.

## 2026-07-10 - P1.5 production Tome schema and fixture

- Added an additive cover-page v2 model while leaving legacy Tome v0 APIs
  versioned and unambiguous.
- Validation resolves files only through the cover-page role index. Filename
  guessing and directory walking would hide producer contract gaps and are not
  part of the consumer boundary.
- Corridor stat-band modes, packed assignments, and selected dynamic-top-k
  exemplars now have typed projections and semantic blockers. Delivery route
  remains provenance and cannot alter target meaning.
- Capability inspection reports valid-but-unsupported artifacts separately
  from malformed artifacts, preserving future roles and surfaces for explicit
  negotiation.
- Contract packages the one canonical deterministic production fixture;
  downstream Student CI must consume it rather than maintaining a private copy.

## 2026-07-10 - P1.5 acceptance receipt

- Recorded immutable Tome, Contract implementation, and Student baseline commits
  alongside the canonical fixture digest and exact verification results.
- The shared production fixture gate passes with no blockers or warnings, so
  P1.5 is complete and Student P1.6 is unblocked. P1.7 remains ordered behind
  P1.6.
- The receipt explicitly avoids claims about model quality, Student training,
  payload loaders, or delivery-path quality parity.

## 2026-07-31 - M6E RADJAX-Tome v3 Contract Publication

- RADJAX-Contract 0.2.0 packages a byte-identical copy of the approved
  RADJAX-Tome portable v3 contract source and conformance corpus.
- The new resource-discovery API exposes static assets only; Contract does not
  import Tome, and existing v2 APIs and fixtures remain unchanged.
- The package checksum inventory pins every portable asset. Tome verifies this
  release before demoting its local source tree to an offline checked mirror.

## 2026-07-31 - M7E RADJAX-Tome Streaming Contract Publication

- RADJAX-Contract 0.3.0 packages a byte-identical copy of Tome's approved v2
  streaming-contract assets, including the v4 cover, acyclic manifests, JSONL
  indexes, semantic identity, recipes, vectors, compatibility descriptors, and
  conformance catalog.
- New v2 resource discovery is additive beside the established v1 API; existing
  Contract v2 production APIs and fixtures are unchanged. Contract remains a
  static contract owner and never imports Tome.
- Package-data and checksum tests pin source and installed asset integrity.

## 2026-07-31 - M7E Portable Validator Ownership Correction

- Contract 0.3.1 owns the reusable, stdlib-only M7 streaming validator beside
  the published v2 schemas and resources. Tome retains only a command-line
  forwarding shim, so producer and consumer conformance have one implementation.
- The validator supports safe sequential archive spooling and bounded-memory
  directory validation without importing RADJAX-Tome.

## 2026-07-31 - M7 corrective direct streaming candidate

- The untagged 0.3.2 candidate replaces archive-wide temporary extraction with
  a direct sequential v4 archive reader. It retains only bounded control-plane
  data and disk-backed JSONL indexes while validating and yielding one payload
  record at a time.
- Safe noncanonical container metadata remains a permissive warning and a
  strict-mode rejection. A cover declaration that disagrees with the physical
  directory/tgz/rtome container now fails explicitly as `transport_mismatch`.
- This is a corrective branch candidate only: v0.3.1 and its published assets
  remain immutable, and no release or tag was created.

## 2026-07-31 - M7 direct-stream index linkage hardening

- The direct shard stream additionally checks each payload-index row's
  `shard_sha256` against the streamed shard-index authority, preserving the
  native validator's address/linkage obligation without retaining records.

## 2026-08-01 - Restore accepted M7 production boundary

- Reverted only the unauthorized native-v3 Student-consumption publication and
  its receipt-pin follow-up from `main` using ordinary additive revert commits.
- The published accidental state and its source branch remain reachable through
  dedicated `reference/unauthorized-student-consumption-contract*` branches.
- M7 v2 streaming assets, direct validation behavior, and historical v1/v2/v3
  production contract surfaces remain in place. No replacement consumption
  design is introduced by this restoration.

## 2026-08-01 - C1 native-v3 Student-consumption normative boundary

- Added a closed, specification-only Contract draft for
  `native_v3_student_v1`: a native-v3 cover-family extension, a separate
  consumption semantic identity, path-independent role/instance bindings,
  fixed numeric policy, deterministic issue ordering, archive limits, and
  versioned descriptor/result schemas.
- Legacy v3 admission remains historical and unmodified.  The draft explicitly
  separates Student batch resources, Contract-only validation evidence,
  optional diagnostics, and provenance-only Path A/Path B facts.
- C1 contains an independently constructed manifest fixture and complete named
  adversarial-code catalog.  It does not implement a resolver, publish an
  asset, modify Tome, or claim Student batch/training behavior.  C2 remains
  behind independent C1 review.

## 2026-08-01 - C1 review hardening

- The normative assets are now checksum-closed after review changes and are
  declared as package data.  The valid manifest is validated through its
  external semantic-identity schema reference, while negative schema checks
  cover a missing required role, a duplicate resource declaration, and a
  target-shard row-range omission.
- The cover-family extension requires the consumption-manifest inventory
  declaration, and the adversarial catalog binds every declared rejection code
  to one named deterministic mutation with its primary issue tuple.  Wheel
  inventory coverage is exercised where the configured setuptools build backend
  is available; the current Python 3.14 runner lacks that backend and skips
  only that environment-dependent assertion.
- `row_range_declaration` is explicitly required validation evidence.  The C1
  fixture now proves the ordered identity-to-manifest resource projection,
  resource/role-instance uniqueness, and one-to-one inventory bindings.  C2
  must make those cross-document relations and the cover manifest-hash to
  inventory-hash equality executable before resolving any descriptor.

## 2026-08-01 - C1 normative relation clarification

- Clarified the portable record's one-to-one logical-resource mapping and its
  cover-to-content-manifest raw-integrity relation.  This is a documentation
  correction only; no profile, schema, fixture, identity, or runtime behavior
  changed.

## 2026-08-01 - C2 portable asset discovery

- Added a dedicated, traversal-safe public discovery surface for the checked-in
  native-v3 Student-consumption contract assets.  It exposes only the C1 draft
  identifier and draft publication version; it does not imply a release, a
  resolver, or a Student runtime dependency.

## 2026-08-01 - C2 resolver foundation

- Added the new structured native-v3 Student-consumption resolver foundation.
  It recognizes only the closed v3 consumption cover extension, treats legacy
  v3 as explicitly not consumable, validates the sidecar's raw inventory
  binding, and resolves roles only from sidecar role/instance declarations.
- Archive handling remains private and safety-gated.  Full resource-content,
  join, and semantic-digest validation is still required before C2 acceptance;
  this commit does not authorize publication or Tome integration.

## 2026-08-01 - C2 binding and identity hardening

- The resolver now rejects duplicate JSON keys, non-object metadata, ambiguous
  inventory/logical-payload bindings, mismatched raw sizes, missing required
  roles, and inconsistent base or consumption semantic identity digests before
  it returns a descriptor.  Materialized local artifact tests cover the valid
  sidecar route and malformed cover failure.

## 2026-08-01 - C2 archive-admission hardening

- Student-consumption archive admission now has bounded member, per-member,
  total-size, compression-ratio, safe-path, regular-file, and duplicate-member
  checks.  It rejects a container whose declared transport does not match its
  actual directory, `.rtome`, or gzip-wrapped tar form.

## 2026-08-01 - C2 verified resource opening

- Added a context-managed verified-resource interface keyed by stable sidecar
  `resource_id`, never caller-provided paths.  It completes admission first and
  rechecks the selected member's raw size and streaming SHA-256 before yielding
  bytes, with deterministic cleanup for directory and archive transports.

## 2026-08-01 - C2 target-shard semantic admission

- Target-shard resources are now decoded as NPZ only and checked for required
  `int32` input, mask, and length arrays; rank/shape agreement; vocabulary
  domain; prefix masks; and mask-to-length equality.  This preserves the
  declared teacher-logit-position alignment without applying a loader shift.

## 2026-08-01 - C2 corridor and exemplar semantic primitives

- Added Builder-independent, path-neutral Contract primitives for corridor
  assignment/mode validation and exemplar/passport validation.  They own
  Contract tolerance constants and deterministic TSC findings, while the public
  resolver continues to own transport, integrity, and descriptor assembly.
- The descriptor schema now explicitly separates `validation_resources` from
  corridor and exemplar batch resources so a consumer cannot mistake evidence
  for a training input.

## 2026-08-01 - C2 resolver semantic integration

- The public resolver now invokes the portable corridor and exemplar primitives
  over materialized resource files after integrity and target checks.  The
  focused fixture includes actual target, assignment, observed-statistics, and
  mode resources; no resolver branch derives a role from its locator.

## 2026-08-01 - C2 semantic adversarial proof

- Added a materialized artifact mutation that refreshes raw inventory and
  sidecar hashes after changing a target token.  The resolver still rejects it
  as `TSC034_TOKEN_DOMAIN`, proving semantic validation is independent of raw
  integrity validation.

## 2026-08-01 - C2 archive transport equivalence

- Added a real `.tgz` resolution proof for the same explicit consumption
  sidecar.  The resolver reports the physical archive transport while retaining
  the declared consumption identity; a directory/container declaration mismatch
  remains a hard error.

## 2026-08-01 - C2 descriptor/result schema proof

- The resolver's serializable descriptor and result are now validated against
  their checked-in versioned JSON Schemas in the materialized artifact test.
  Tuple-backed implementation details are normalized to contract arrays at the
  public serialization boundary.

## 2026-08-01 - C2 RTome transport proof

- Added the plain-tar `.rtome` equivalent of the native-v3 consumption
  transport proof.  Directory, gzip-wrapped tar, and RTome now each exercise
  the same explicit sidecar resolver path with physical transport facts kept
  outside consumption identity.

## 2026-08-01 - C2 physical-relocation identity proof

- Added a materialized relocation test: moving a target resource and updating
  its legacy logical/inventory locators requires fresh raw-manifest binding but
  preserves the separate consumption semantic digest.  This proves role and
  instance remain the semantic authority rather than physical placement.

## 2026-08-01 - C2 Path A/B provenance equivalence

- Added the paired delivery-path proof: changing the resolved artifact's Path
  A/Path B provenance and refreshing raw sidecar binding preserves consumption
  semantic identity.  Delivery provenance remains auditable but is not batch
  meaning.

## 2026-08-01 - C2 negotiation fail-closed checks

- Resolver admission now rejects a sidecar with an unsupported digest method or
  nonempty/unknown required capability list before any dependent resource work.
  The materialized fixture declares its required native-v3 Student profile
  explicitly, matching the closed cover extension.

## 2026-08-01 - C2 role and join admission hardening

- Resolver admission now requires all three declared cross-resource joins and
  rejects a resource whose classification disagrees with its closed semantic
  role.  The materialized fixture uses real batch, validation, and provenance
  classifications rather than treating every role as validation evidence.
- A raw-integrity-refreshed sidecar mutation with only one join now fails the
  public resolver as `TSC013_BINDING_ABSENT`, proving the check is semantic
  admission rather than a stale-manifest artifact.

## 2026-08-01 - C2 published-schema admission

- Resolver admission now loads the packaged manifest and external semantic
  identity schemas and validates the source sidecar before cross-document
  resolution.  `jsonschema` is a runtime Contract dependency because this is a
  portable validation guarantee, not a test-only assertion.

## 2026-08-01 - C2 closed-cover and binding-order hardening

- Resolver admission now validates the complete published closed cover schema
  before resolving its sidecar.  The source fixture carries the required v3
  cover-family sections and complete inventory entry shape, so a partial cover
  cannot masquerade as a supported Student-consumption artifact.
- Duplicate role/instance bindings and noncanonical role/instance order now
  produce their distinct published `TSC011` and `TSC012` outcomes.  Archive
  extraction copies bounded blocks and rejects premature member EOF instead of
  materializing each tar member with an unbounded `read()`.

## 2026-08-01 - C2 material exemplar/corridor admission

- The material resolver fixture now carries a real example registry, selected
  passport, selected exemplar payload, and packed corridor coordinates.  The
  resolver maps declared registry identities onto declared assignment
  coordinates before validating exemplar-to-corridor linkage; no physical path
  supplies that meaning.
- Dynamic top-k validation now enforces active token uniqueness and vocabulary
  membership, descending active probabilities, and canonical inactive token ID
  zero in addition to Contract-owned probability and log-probability rules.

## 2026-08-01 - C2 executable transport canonicality

- Safe archive admission now classifies noncanonical gzip wrapper or tar member
  metadata as the documented `TSC020_TRANSPORT_NONCANONICAL` warning.  Strict
  validation promotes that warning to rejection; permissive validation remains
  safe and explicit.  The warning is intentionally separate from the closed
  rejection-code corpus rather than pretending that a repack is unsafe.

## 2026-08-01 - C2 target-shard admission and suppression

- Target resources now require contiguous nonempty global row ranges before
  their array content is inspected.  Public mutations prove distinct dtype,
  rank/shape/axis, mask/length, token-domain, and row-range outcomes.
- A failed target prerequisite suppresses dependent corridor/exemplar checks,
  preserving the documented deterministic issue policy rather than producing
  a cascade of coordinates derived from an invalid target shard.

## 2026-08-01 - C2 binding and identity mutation proof

- The public resolver now has material adversarial proofs for missing required
  roles, ambiguous inventory, inconsistent semantic bindings, invalid inventory
  references, unavailable manifest, resource corruption, stale consumption
  digest, and base semantic-root disagreement.  Required-role absence is
  classified before schema-dependent resolution while the published schema
  remains independently strict.

## 2026-08-01 - C2 branch validation checkpoint

- The cache-cleared Contract suite passes with 135 passed and 1 skipped in the
  current local interpreter.  Static validation follows the repository Ruff,
  formatting, compile, and diff checks; the skipped installed-wheel test is
  environment-specific and remains an explicit release-gate check.

## 2026-08-01 - C2 archive canonicality and hostile transport proof

- Archive canonicality now includes strictly ascending member paths as well as
  deterministic gzip and tar metadata.  A canonical archive passes strict
  admission; a safe reordered archive reports noncanonical transport
  permissively and fails strict admission.
- Public material cases now prove unsafe link rejection and a raw-integrity
  refreshed but wrong target container rejection, closing two formerly
  catalog-only adversarial outcomes.

## 2026-08-01 - C2 semantic-schema precision

- The portable consumption-identity schema now enumerates vocabulary size and
  tokenizer identity, sequence length and teacher-logit alignment, the closed
  three-join set, and the fixed selection integration authority hash.  The
  cover extension also requires the native identity bindings and a supported
  delivery transport rather than accepting an arbitrary object at those
  consumer-relevant boundaries.

## 2026-08-01 - C2 hostile archive matrix expansion

- Public archive admission now has material traversal, duplicate-member,
  hard-link, truncated gzip, and configured member-limit cases.  Truncated
  gzip EOF is normalized to the documented unsafe-transport outcome rather
  than escaping the portable validation result.

## 2026-08-01 - C2 deterministic warning evidence

- A repeated material noncanonical archive proof now asserts the complete
  warning tuple is locator-ordered and stable.  This covers the public warning
  API separately from issue ordering and prevents tar iteration order from
  becoming externally observable behavior.

## 2026-08-01 - C2 material delivery corpus

- The deterministic material native-v3 Student artifact now has public
  delivery proof as a directory, `.rtome`, and strict-canonical `.tgz`.  This
  establishes the transport-neutral corpus base that adversarial mutations use
  instead of relying only on schema vectors.

## 2026-08-01 - C2 material corridor mutation runner

- The material corpus now executes integrity-refreshed packed-assignment
  mutations through the public resolver for missing coordinates, duplicates,
  unknown modes, and negative weights.  Supporting observed-statistics lengths
  are adjusted where necessary so each case proves its advertised complete
  deterministic tuple rather than a prerequisite failure.

## 2026-08-01 - C2 material exemplar mutation runner

- Material selected-exemplar mutations now exercise passport joins, rank,
  dynamic top-k masks, probability mass, corridor linkage, and delivery-path
  provenance through the public resolver.  Invalid passport joins suppress
  dependent linkage and missing-passport cascades, preserving the documented
  primary complete issue tuple.

## 2026-08-01 - C2 material admission and identity mutations

- The material corpus now exercises legacy/profile and cover-version
  negotiation, required capabilities, digest methods, transport declaration,
  stale consumption identity, and base native-v3 identity disagreement through
  the public Contract API.

## 2026-08-01 - C2 material coordinate and mode-bound mutations

- Public material validation now proves invalid extra assignment coordinates
  and inverted mode bounds.  Mode-table structural failure suppresses derived
  unknown-mode and statistics cascades, retaining its deterministic primary
  `TSC044` outcome.

## 2026-08-01 - C2 archive safety-limit corpus

- The material public-resolver corpus now invokes each archive safety branch:
  per-member byte limit, aggregate byte limit, compression-ratio limit, and
  FIFO/special member rejection.  Each normalizes to `TSC021` without exposing
  tar implementation exceptions.

## 2026-08-01 - C2 pinned material corpus policy

- The Student conformance catalog now names its checksum-pinned normative
  source vector and the public deterministic materializer, following the
  repository's established temporary-fixture policy.  This avoids a second
  binary-fixture authority while preserving portable directory, rtome, and
  canonical tgz execution evidence.

## 2026-08-01 - C2 current-head validation evidence

- Cache-cleared Contract validation at `eea03ba` passed with 168 passed and
  1 environment-skipped test.  Ruff lint, formatting, compilation, and
  `git diff --check` also passed; the only working-tree item was the preserved
  unrelated `.DS_Store`.

## 2026-08-01 - C2 vector-derived material corpus

- The material constructor now derives its role sequence from the
  checksum-pinned native-v3 specification vector.  Directory, rtome, and
  canonical tgz admissions are proven to resolve one identical consumption
  semantic digest, rather than merely returning success independently.
