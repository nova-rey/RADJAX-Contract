# RADJAX-Contract

RADJAX-Contract defines the Tome handshake shared by RADJAX-Tome and
RADJAX-Student.

RADJAX-Tome emits Tomes. RADJAX-Student consumes Tomes. RADJAX-Contract defines
and validates what a valid Tome is. Artifact files are the API between Tome and
Student; Python imports between those producer and consumer repos are not.

This package does not load teacher models, train students, run JAX kernels, or
depend on PyTorch/Transformers. Teacher execution details are RADJAX-Tome
internals unless written into Tome provenance. Student training configs,
optimizer state, runtime selection, checkpoint internals, and architecture
configs are RADJAX-Student internals unless they become Tome consumption
boundary data.

The original `qrwkv-xla` repository is historical source material for the split
and is not modified by this Contract hardening phase.

## Current Tome Contract

A minimal Tome is a portable teacher-output artifact directory:

```text
tome_dir/
  manifest.json
  records.jsonl
  logits.npy
```

The current implemented payload format is `dense_logits_v0`, represented by a
finite floating NumPy array shaped `[records, sequence, vocab]`.

The primary public surface is:

```python
from radjax_contract import (
    TomeManifest,
    TomePayloadFormat,
    TomeRole,
    TomeShard,
    TomeRecord,
    TomeValidationResult,
    VocabContract,
    TokenizerFingerprint,
    stable_hash,
    file_sha256,
    validate_tome,
    validate_tome_split_disjointness,
)
```

Future payload names are reserved for top-k/tail, cascaded soft labels, dynamic
top-k cascading buckets, fingerprint corridors, and exemplar reservoirs. They
are recognized as names but intentionally fail validation with clear blockers
until their contracts are implemented.
