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
  cover_page.json
  manifest.json
  records.jsonl
  logits.npy
```

The current implemented payload format is `dense_logits_v0`, represented by a
finite floating NumPy array shaped `[records, sequence, vocab]`.

## Tome Cover Page

`manifest.json` is the strict machine contract. `cover_page.json` is the
readable summary and routing index. `records.jsonl` and payload files such as
`logits.npy` are the actual Tome contents.

The Cover Page summarizes the teacher, corpus, contents, explicit compression,
behavioral fingerprint status, split role, and expected student consumption
adapter. Validation requires the Cover Page to agree with the manifest and, for
implemented dense logits Tomes, with the records and payload shape.

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
