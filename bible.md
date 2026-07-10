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
