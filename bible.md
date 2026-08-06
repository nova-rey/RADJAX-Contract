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

## 2026-08-01 - C2 canonical NPZ assignment vector

- The normative native-v3 Student vector now declares `corridor_assignment`
  as NPZ with explicit inventory-backed `resources/03.npz` delivery binding.
  Contract fixture checks reject the former legacy JSON/path assumption; legacy
  JSON remains a negative compatibility surface rather than canonical payload
  meaning.

## 2026-08-01 - C2 truthful material vector correction

- The checksum-pinned native-v3 Student conformance vector now describes the
  actual deterministic material corpus: explicit inventory-backed locators,
  NPZ packed corridor assignments, resource identities, encodings,
  classifications, consumption declarations, vocabulary, sequence contract,
  joins, authority, provenance, and recomputed consumption semantic digest.
  The public materializer consumes and asserts that complete declaration rather
  than deriving only its role list. The expected descriptor vector pins the
  resulting profile, base identity, vocabulary, sequence, resource identities,
  and consumption digest.
- `corridor_assignment` is schema/profile constrained to NPZ. A legacy JSON
  assignment remains an executable adversarial case and deterministically
  returns `TSC030_CONTAINER_ENCODING_MISMATCH`; dependent exemplar checks are
  suppressed after that prerequisite encoding failure.
- Focused vector, digest, materialization, resolver, and adversarial tests
  passed (87 passed, 1 environment-skipped). The isolated installed-wheel
  package-data test also passed with the configured setuptools build backend.

## 2026-08-01 - C3 v0.4.0 release candidate

- The accepted native-v3 Student-consumption profile is no longer declared as
  a draft. Its immutable contract publication version is `1.0.0`; the Contract
  distribution release candidate is `0.4.0`. This is an additive public API
  and conformance-contract release, preserving all existing v1/v2 and M7
  assets. The final tag, release, and package digests are recorded only after
  verification and exact-main publication.

## 2026-08-01 - C3 v0.4.0 immutable publication receipt

- `main` fast-forwarded from `e97e0593ba727855fa1a62bc5ca97d12d189a5e3`
  to the C3 candidate `77b6e9f12e6f20f0bdfc9121b062b1bd21661889`. Annotated
  tag `v0.4.0` dereferences to that exact commit; no prior tag was moved.
- GitHub release `v0.4.0` publishes the source distribution
  `radjax_contract-0.4.0.tar.gz` with
  `sha256:905eac5a1ad0864e2d84050c88a53d6d53bab656749a4fa2a272379ed8713d59`
  and the wheel `radjax_contract-0.4.0-py3-none-any.whl` with
  `sha256:196d69fb694fd1ac4735438451fe555568db5fb4950536e4e23ae1f54a0baf4f`.
  The release API reports those same digests. Tome may pin only this tag,
  commit, and verified publication assets; it must not pin the former untagged
  `0.3.2` candidate.

## 2026-08-01 - C4 native-v3 Student-consumption v2 repair candidate

- The released `native_v3_student_v1` sidecar binding is preserved as
  historical v0.4.0 behavior. Its requirement that every derived resource
  appear in native-v3 `identity.training_payload` cannot truthfully represent
  new sidecar material without changing the base semantic root. The v2 profile
  therefore binds independently digested derived resources by stable role,
  instance, resource identity, semantic digest, and raw inventory locator;
  it deliberately forbids a legacy training-payload binding.
- V2 preserves the native-v3 base semantic digest while separately hashing the
  complete ordered consumption projection. Canonical JSON/JSONL and framed,
  little-endian NPZ member semantics are normative. Exact NPZ axes use the
  real assignment members (`position_example_index`, `position`, `mode_id`,
  `weight`) and assignment-aligned observed statistics. Physical relocation
  changes delivery/cover integrity but not the v2 consumption digest.
- Focused v2 resolver, schema, vector, materialization, and historical-v1
  compatibility tests passed: 40 passed, 1 environment-skipped. No v0.4.0
  asset or tag was changed. Release version metadata and publication are
  intentionally deferred until the complete v0.4.1 verification gate.

## 2026-08-01 - C4 v0.4.1 immutable publication receipt

- `main` contains the reviewed v2 profile at
  `a6877178d5f07d68f5e0bc28419d0e8e1a58890e`; annotated tag `v0.4.1`
  dereferences to exactly that commit. No existing release or tag was moved.
- GitHub release `v0.4.1` publishes
  `radjax_contract-0.4.1.tar.gz`
  (`sha256:37ad0bc1cde5c41118f8a1dd3ccd45eea5f2b66a4054c7e9f4c8852558574506`)
  and `radjax_contract-0.4.1-py3-none-any.whl`
  (`sha256:4edb26ae027d8c6c81e8dffd30130eba9be091bebd5b5bdda2671558d20640dd`).
  Tome may now pin only this immutable tag, commit, and verified asset tree.

## 2026-08-01 - C5 native-v3 Student-consumption v3 candidate

`native_v3_student_v2` remains an immutable released profile.  It did not
semantically bind the row-range, delivery-receipt, and authority-reference
sidecars strongly enough to correct safely under the same public profile ID.
The new `native_v3_student_v3` profile is therefore an explicit, opt-in
compatibility boundary: it preserves the base native-v3 semantic root and the
separate derived consumption identity while requiring closed evidence bodies
and cross-checking their counts, delivery semantics, and authority reference.
There is no v3-to-v2 fallback.  This candidate has not been released; the
next minor publication is planned as `v0.5.0` after complete verification.

## 2026-08-01 - C5 v0.5.0 immutable publication receipt

- `main` contains the reviewed v3 profile at
  `e5f2c3ed79cfc0e6eebf64a22b96a656818b5f39`; annotated tag `v0.5.0`
  dereferences to exactly that commit. Existing profiles and tags, including
  `native_v3_student_v2` at `v0.4.1`, were not changed.
- GitHub release `v0.5.0` publishes
  `radjax_contract-0.5.0.tar.gz`
  (`sha256:227e64a3b1089d4ccca101353bfd7d7f2e4fbd7ca67ef39c4930958600866bea`)
  and `radjax_contract-0.5.0-py3-none-any.whl`
  (`sha256:816946f150fba4a2eaadff4ce72708ca1295b4ce1b9228962eedc0a5e8e142af`).
  Tome may pin this immutable release and verify its checked-in offline mirror.

## 2026-08-01 - C5 v0.5.1 archive compatibility candidate

- V3's extracted-directory compatibility adapter preserved an original `tgz`
  declaration while delegating to v2, which correctly validates only the
  temporary directory and therefore rejected a valid archive as a transport
  mismatch. The candidate records the original archive validation at v3 then
  declares the temporary compatibility stage as a directory for v2 only.
- This is an additive patch to v3 delivery resolution: profile IDs, schemas,
  semantic identity, published `v0.5.0`, and historical v1/v2 validation are
  unchanged. Focused directory and tgz v3 resolver tests passed before review.

## 2026-08-01 - C5 v0.5.1 immutable publication receipt

- `main` contains the reviewed archive-resolution repair at
  `f9c9278b6a467a6ba7a3972e1644bfc3d13abd6b`; tag `v0.5.1` dereferences to
  that exact commit. The published v0.5.0 tag and all v1/v2/v3 contract assets
  remain unchanged.
- GitHub release `v0.5.1` publishes
  `radjax_contract-0.5.1.tar.gz`
  (`sha256:83c3b48300fc6290e02299841046411455f504915bd194ca152c8b614b59a7df`)
  and `radjax_contract-0.5.1-py3-none-any.whl`
  (`sha256:6cd91f25624c11de01175faf6267cc1baa114b113f03aa805e0d0b9e062acbdf`).

## 2026-08-01 - C4 native-v3 Student-consumption v4 candidate

- The published `native_v3_student_v3` profile remains immutable. This additive
  v4 candidate keeps `delivery_receipt` and `authority_reference` manifest- and
  raw-integrity-bound and validates their closed bodies, but excludes their
  body digests from the v4 batch-semantic identity projection.
- The new Path A/Path B regression changes only valid delivery provenance and
  proves one resolved consumption digest. Existing v2/v3 profile IDs and
  assets remain available without fallback or reinterpretation.

## 2026-08-01 - C4 v0.6.0 immutable publication receipt

- `v0.6.0` is annotated at
  `b1209f21fef9405776a757f1a5749d3152bbc3c6`. It publishes the additive
  `native_v3_student_v4` profile; v2 and v3 profile sources, validators, and
  static assets remain unchanged.
- GitHub release artifacts are
  `radjax_contract-0.6.0-py3-none-any.whl`
  (`sha256:c237f6b8be3bb0b8dc95181a80350c7a5dddf4d2dcb23be8ad1ef0b6f8c620c2`)
  and `radjax_contract-0.6.0.tar.gz`
  (`sha256:52899b277763d3325467f34eb0a482445af621fe1f712d1da461061882d7720d`).

## 2026-08-01 - Phase 5 C1 language/tokenizer binding normative candidate

- Added the closed `native_v3_student_v5` normative asset tree. Its sole new
  semantic declaration is `LanguageTokenizerBindingV1`: immutable tokenizer
  identity, complete content inventory, inventory-bound canonical vocabulary
  JSONL, vocabulary identity/domain, and deterministic token declarations.
- V5 canonical digests exclude delivery paths, transport, raw inventory
  metadata, wrapping, archive metadata, and timestamps. Sequence length,
  architecture descriptors, plugin descriptors, loaders, and training policy
  are explicitly outside the Contract binding.
- V1--v4 source assets and behavior were not modified. This is a candidate
  checkpoint only: no release, tag, merge, or publication has occurred.

## 2026-08-01 - Phase 5 C2 generic language/tokenizer resolver candidate

- The public v5 resolver accepts only an explicit v5 binding or fixed v5
  package manifest, computes the normative inventory and binding digests, and
  rechecks every opened resource. There is no v5-to-v4 fallback.
- Vocabulary JSONL is verified as canonical UTF-8/base64 records in exact
  `[0, vocabulary_size)` order. Bounds are enforced only for declared token-ID
  fields; sequence length is absent from this generic contract.
- The resolved descriptor exposes generic tokenizer semantics and verified
  behavior-content resources only. It intentionally contains no architecture
  or plugin projection. Package metadata is the unreleased `0.7.0` candidate;
  no release, tag, merge, or publication has occurred.

## 2026-08-01 - Phase 5 C3 v0.7.0 immutable publication receipt

- `v0.7.0` is annotated at
  `cac3dd21e0d56df5a9e6fd50b20267e0b8960995`. It publishes the additive
  `native_v3_student_v5` generic LanguageTokenizerBindingV1 profile; v1--v4
  profiles, assets, and validation behavior remain immutable.
- Independent review accepted C1/C2. Full wheel-enabled verification passed:
  208 tests, plus Ruff and format checks. GitHub release artifacts are
  `radjax_contract-0.7.0-py3-none-any.whl`
  (`sha256:2e6e39602460133d9c8a9c4a100e3933db5b221ed3503ae05c087d60863a2622`)
  and `radjax_contract-0.7.0.tar.gz`
  (`sha256:2214b9cc64e22e471f98f2c0218124d61701864cd109b31eee8c24e30132fcc0`).

## 2026-08-02 - B2 v6 approved projection freeze

- B2 restarted from the B1-recorded `bae469e` Contract base on an isolated
  unpublished branch. Before any v6 identity-bearing schema or digest, the
  exact selected-passport and authority-reference field sets, ordering,
  canonicalization, exclusions, and identity consequences were frozen in the
  v6 projection record.
- Whole-resource verification is the honest opening unit for ordinary JSONL;
  M7 retains its bounded shard/index record unit. Corridor aggregates remain
  validated diagnostics and are not behavioral authority by default.

## 2026-08-02 - B2 v6 projection freeze evidence correction

- Corrected the preliminary projection record using the actual historical
  producer/model fields: v6 passports retain the evidenced rank, score,
  policy, corridor mode/fingerprint/status, and selection-integration hash;
  the authority reference retains closed selection, score-pass, and delivery
  authority hashes. Unsupported conceptual fields and legacy aliases are
  excluded before v6 schema or digest implementation.

## 2026-08-02 - B2 v6 behavioral authority identity foundations

- Began the explicitly approved additive `native_v3_student_v6` Contract work
  on an unpublished B2 branch. The first foundation establishes distinct,
  framed identities for NPY components and multipart NPY resources, canonical
  JSONL logical record sequences, behavioral-source authority, behavioral
  replay authority, and exact composition provenance.
- Delivery registry entries are mechanically excluded from the behavioral
  authority digest but included in the composition digest. No v1--v5 code,
  profile behavior, or packaged contract asset was changed, and this is not a
  release or a Tome/Student migration claim.

## 2026-08-02 - B2 v6 exact projection identity implementation

- Implemented the approved closed projections for selected passports and the
  authority reference before admitting them to any behavioral digest. Passport
  provenance extensions and authority aliases fail closed; included-field
  changes necessarily change the projected semantic identity.

## 2026-08-02 - B2 v6 packaged-contract discovery checkpoint

- Added additive v6 packaged-asset discovery and wheel inclusion plumbing;
  historical v1--v5 discovery functions remain unchanged. The v6 asset tree
  is still under construction and is not published, tagged, or selected by
  any default profile.

## 2026-08-02 - B2 v6 explicit public dispatch

- Added only an explicit `native_v3_student_v6` branch to the established
  public resolver/opener dispatch surface. No historical profile negotiates or
  falls back to v6.

## 2026-08-02 - B2 v6 resolver foundation

- Added the candidate v6 resolver and verified-opening foundation on the clean
  B2 branch. The subsequent projection correction binds its identity-bearing
  passport and authority inputs to the approved closed field sets; no v1--v5
  resolver behavior was edited.

## 2026-08-02 - B2 v6 resolver projection enforcement

- Wired the approved closed passport and authority-reference projections into
  resource semantic admission. A resource with extra, missing, aliased, or
  otherwise noncanonical authority fields is rejected before it can affect a
  behavioral identity.

## 2026-08-02 - B2 corridor diagnostic identity exclusion

- Corridor aggregate statistic values are validated diagnostics only. The v6
  mode-table semantic projection binds mode IDs and statistic definitions, not
  diagnostic minimum/mean/maximum values.

## 2026-08-02 - B2 multipart raw-integrity enforcement

- V6 multipart NPY resources now require independently declared raw digest and
  size evidence for every component before semantic decoding or identity use.

## 2026-08-02 - B2 declared multipart component opening

- Target and assignment validation now opens only declared component locators;
  no v6 component role is inferred from a fixed filename.

## 2026-08-02 - B2 v6 static identity contract checkpoint

- Added the initial checksum-closed v6 candidate assets: exact profile
  negotiation, the frozen authority/non-authority role inventory, deterministic
  issue ordering, and documented separation of raw, behavioral, and exact
  package identity. The v6 profile explicitly composes v5 and remains false
  for default new production.

## 2026-08-02 - B2 honest ordinary-JSONL verified opening

- Added an explicit ordinary-JSONL opener that performs the whole-member raw
  trust transition before parsing or yielding any record, retains immutable
  verified bytes, and rejects M7 from that API. The raw resource opener is
  documented as a byte opener, not a record-verification promise.

## 2026-08-02 - B2 whole-resource JSONL conformance fixture

- Added a synthetic, clearly non-Tome v6 fixture that composes the immutable
  v5 fixture and proves ordinary JSONL records are yielded only after complete
  resource admission. A post-admission raw-member replacement fails closed.

## 2026-08-02 - B2 selected-exemplar semantic admission

- V6 now applies the established architecture-neutral exemplar/passport
  semantic validator after its own coordinate joins. Dynamic top-k, probability
  mass, selected-rank, corridor linkage, and delivery-provenance failures are
  exposed through one deterministic v6 exemplar issue with source findings.

## 2026-08-02 - B2 corridor-grid authority joins

- V6 full-grid corridor assignments now fail closed when a coordinate names an
  undeclared mode, and every selected passport must agree with the assignment
  mode at its unmasked coordinate. Corridor aggregate diagnostics remain out
  of behavioral identity.

## 2026-08-02 - B2 schema-closed behavioral binding

- Added and checksum-pinned the v6 behavioral-resource binding schema. The
  resolver applies it before registry resolution, so unknown binding/resource
  fields and malformed integrity declarations fail deterministically instead
  of entering semantic identity computation.

## 2026-08-02 - B2 Contract v0.8.0 preparation

- Prepared local package metadata for v0.8.0 and recorded the release
  nonclaims: no tag or publication, no default migration, no Tome or Student
  change, and no assertion that a canonical v6 producer yet exists. The full
  Contract test suite passed with 217 tests.

## 2026-08-02 - B2 bounded M7 resource opening

- Added the explicit `m7_tome_archive` v6 encoding and a separate verified
  opener backed by Contract's established sequential M7 reader. It preserves
  shard/index verification before yield and exposes early-close versus complete
  verification state; ordinary JSONL never silently uses this protocol.

## 2026-08-02 - B2 frozen-projection conformance corpus

- Closed runtime validation over the exact passport field/value domains and
  added a checksum-pinned v6 conformance catalog. Its synthetic cases are
  explicitly Contract-only evidence, while the M7 early-close case is marked
  as inherited protocol coverage rather than a Tome v6 producer claim.

## 2026-08-02 - B2 independent-review M7 repairs

- M7 payload admission now performs incremental exemplar semantic and join
  validation without retaining payload records. Raw integrity hashing is
  chunked, the schema validator exception path is deterministic, and M7
  opening stages an exact verified archive snapshot before streaming to close
  the validation/reopen replacement window. Added a real v6 M7 integration
  fixture for admission, early close, full exhaustion, and tamper rejection.

## 2026-08-02 - B2 M7 inner-exemplar adversarial conformance

- Added a validly rehashed M7 archive whose inner exemplar violates dynamic
  top-k semantics. The generic M7 verifier accepts its rebuilt transport and
  integrity chain; v6 deterministically rejects it through the exemplar
  semantic validator as `BRC027_EXEMPLAR_SEMANTICS_INVALID` with
  `TSC052_DYNAMIC_TOPK_INVALID`.

## 2026-08-03 - P5.U1 strict v6 language projection

- Added `resolve_student_language_binding()` as an exact-profile, strict-only
  public projection over one authoritative v6 admission. It returns the
  already-validated `LanguageTokenizerBindingDescriptor` and fails closed if
  its canonical digest differs from the admitted v6 descriptor.
- Proved canonical directory and `.tgz` parity, embedded-binding and projected
  digest tamper rejection, historical-profile exclusion, inherited archive
  safety and size limits, absence of temporary extraction paths, and installed
  wheel visibility. The full Contract suite passes with 230 tests; the exact
  Tome P5.U1 fixtures at `8508b1351d0ed8d6a3a14049e4d6f8a849c33cf1`
  project the same canonical language binding digest.
- Advanced additive package metadata to `radjax-contract` 0.8.1 without v6
  schema, semantic identity, profile-default, or historical v5 API changes.

## 2026-08-03 - P5.3 strict v6 multipart component opening

- Added `open_verified_student_resource_component_v6()` and the typed
  `VerifiedStudentResourceComponentV6` result. The strict exact-v6 context
  manager selects only a component declared by an admitted multipart resource,
  reuses Contract's existing safe artifact root, and rechecks raw size and
  SHA-256 before yielding a bounded read-only stream.
- The public result carries resource/component identity, role, schema,
  encoding, axes, resource semantic identity, raw digest, and raw size. It
  deliberately omits physical member and temporary extraction locators, and
  leaves byte decoding to Student.
- Proved directory/archive byte equivalence, resource and component selection,
  locator/size/byte tamper rejection, post-admission replacement rejection,
  historical-profile and non-strict rejection, inherited archive safety and
  limits, and installed-wheel visibility. The full Contract suite passes with
  250 tests.
- Against Tome `8508b1351d0ed8d6a3a14049e4d6f8a849c33cf1`, every declared
  `target_shard/default` component opens identically from `student/` and
  `student.tgz`: `attention_mask` is 160 bytes at
  `sha256:675a218989692894cb472ebb39984e1e7a83fab33ecc78a416a8629a475e1f89`,
  and `input_ids` is 256 bytes at
  `sha256:7d09f5ad2928dfeb3a7fa8c9d21afe25c0f2a2db30b2f1a8f2b1b79fea35e893`.
- Advanced additive package metadata to `radjax-contract` 0.8.2 without v6
  schema, semantic identity, archive reader, decoder, or historical API
  changes.

## 2026-08-06 - P5.3 aggregate verified multipart access

- Added `open_verified_student_multipart_resource_v6()` and the frozen
  `VerifiedStudentMultipartResourceV6` projection. One strict exact-v6
  admission now yields an immutable mapping of every component declared by one
  admitted multipart resource through the existing Contract-owned safe archive
  root.
- Added `VerifiedStudentMultipartComponentV6` with canonical NPY encoding,
  dtype, shape, and derived component semantic identity while preserving the
  accepted single-component model unchanged. Contract recomputes each component
  identity and the enclosing multipart semantic identity before yielding
  bounded read-only streams; Student still owns payload decoding.
- Physical component locators and temporary extraction paths remain absent
  from both public models and their serialized metadata. Unknown resources,
  component lookup, cross-resource substitution, raw tampering,
  post-admission replacement, historical profiles, non-strict use, unsafe
  archives, and configured archive limits fail closed.
- Against Tome `8508b1351d0ed8d6a3a14049e4d6f8a849c33cf1`, directory and
  `.tgz` aggregate objects and bytes match for all six declared components of
  `target_shard/default` and `corridor_assignment/default`, including dtype,
  shape, axes, raw digest, raw size, component identity, and resource identity.
- The full Contract suite passes with 267 tests; Ruff, formatting, and
  installed-wheel public exports pass. Advanced package metadata to
  `radjax-contract` 0.8.3 without schema, semantic-identity, language,
  whole-resource, JSONL, M7, or archive-semantics changes.
