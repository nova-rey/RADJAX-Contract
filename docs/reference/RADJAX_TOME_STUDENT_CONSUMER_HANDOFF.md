# RADJAX Tome Artifact: Student-Side Consumer Handoff

**Canonical handoff version:** 1.1  
**Review status:** accepted for P1.5 production alignment  
**Reviewed producer baseline:** `nova-rey/RADJAX-Tome@c8fb9ac4d92a33d8342c2249bae939e21221125a`

> P1.5 clarification: this document describes the accepted producer semantics
> at the reviewed baseline and the contract P1.5 must preserve. The baseline
> cover page indexes core sidecars, top-level corridor files, and target shards;
> P1.5 adds complete role entries for packed assignment files and selected
> exemplar files and therefore emits a new cover-page version. Current producer
> output represents `dynamic_top_k` as a metadata object containing policy and
> effective-k facts; the boolean shown in the illustrative payload below is not
> the normative field shape. These clarifications are versioned here rather
> than silently changing the meaning of handoff version 1.0.

**Audience:** RADJAX-Student developers  
**Producer:** `RADJAX-Tome`  
**Current reference line:** `nova-rey/RADJAX-Tome`, commit family through `c8fb9ac`  
**Purpose:** describe what a completed Tome artifact contains, how its files relate to one another, what the student may safely depend on, and which files are diagnostic rather than training-critical.

---

## 1. Executive summary

A **Tome** is the teacher-produced artifact handed to the student side.

It contains two distinct kinds of teacher guidance:

1. **Fingerprint corridors** — broad, low-byte behavioral targets. Each token position is assigned to a coarse behavioral mode. Each mode contains acceptable min/max bounds for five output-distribution statistics.
2. **Selected exemplars** — a smaller set of interesting token positions with sharper teacher information: selected token IDs, probabilities/log-probabilities, dynamic top-k metadata, bucket masses, tail mass, and linkage back to the corridor mode.

The student should treat these as two separate training surfaces:

```text
corridor pass -> checkpoint -> exemplar pass -> checkpoint
```

The student should not assume a mixed objective unless a later experiment explicitly requests one.

---

## 2. Stable semantic contract

The student side may safely build around these invariants.

### 2.1 Artifact identity and provenance

A Tome identifies:

- the teacher model;
- the tokenizer and vocabulary contract;
- sequence length;
- target type;
- number of examples;
- number of target shards;
- corpus provenance;
- teacher-model provenance;
- validation status;
- file hashes and sizes through the cover sheet.

### 2.2 Corridor contract

For every valid corridor target position, the artifact provides:

- a source example identity;
- a token position within that example;
- a `mode_id`;
- a training weight;
- a mode table entry containing bounds for:
  - `entropy`
  - `top1_margin`
  - `top8_mass`
  - `top32_mass`
  - `tail_mass`

Current mode discovery is:

```text
stat_bands_v0
```

The mode key is formed from:

```text
entropy_bin × top1_margin_bin × top32_mass_bin
```

Mode IDs are **artifact-local**. Never assume that mode `17` has the same meaning in two different Tomes.

### 2.3 Exemplar contract

A selected exemplar identifies:

- source example;
- selected token position;
- selection score and policy;
- selected teacher token IDs;
- selected probabilities and log-probabilities;
- an effective dynamic top-k;
- top mass and tail mass;
- bucket masses;
- teacher entropy;
- linked `corridor_mode_id`;
- optional diagnostic `corridor_fingerprint_id`;
- linkage status.

The selected exemplar payload is a separate training resource from the corridor assignment table.

---

## 3. Representative artifact layout

A completed selected-corridor Tome currently looks approximately like this:

```text
<tome-root>/
├── cover_page.json
├── metadata.json
├── vocab_contract.json
├── teacher_manifest.json
├── emission_config.json
├── validation_report.json
├── production_build_report.json
├── delivery_report.json
├── production_progress.json              # operational; may be absent in older artifacts
├── run_manifest.json                     # streaming/build operational state
├── shards/
│   ├── shard-00000.npz
│   ├── shard-00001.npz
│   └── ...
├── corridors/
│   ├── corridor_summary.json
│   ├── corridor_summary.txt
│   ├── corridor_modes.json
│   ├── corridor_fingerprints.json
│   ├── mode_assignments.json
│   └── mode_assignments/
│       ├── position_example_index.npy
│       ├── position.npy
│       ├── mode_id.npy
│       ├── weight.npy
│       ├── fingerprint_index.npy          # diagnostic; not required for corridor loss
│       └── examples_metadata.jsonl
├── leaderboards/
│   ├── leaderboard_report.json
│   └── selected_exemplars.json
└── selected_exemplars/
    └── selected-exemplars-00000.json
```

Not every historical Tome has every operational/report file. The student should validate required semantic files through `cover_page.json`, `metadata.json`, corridor manifests, and the selected exemplar manifest rather than blindly walking the directory tree.

---

## 4. `cover_page.json`

The cover sheet is the first file a consumer should read.

Current identity fields include:

```json
{
  "artifact_kind": "radjax_tome",
  "cover_page_version": 1,
  "tome_version": 1,
  "layout": "unpacked_directory",
  "created_by": "...",
  "created_at": "...",
  "source_artifact_type": "teacher_textbook",
  "teacher": {},
  "tokenizer": {},
  "targets": {},
  "contents": [],
  "validation": {},
  "claims_not_made": {}
}
```

### 4.1 Teacher section

Representative fields:

```json
{
  "model_id": "...",
  "model_family": "...",
  "backend_type": "gpu_torch",
  "local_files_only": true,
  "allow_downloads": false
}
```

### 4.2 Tokenizer section

Representative fields:

```json
{
  "tokenizer_id": "...",
  "tokenizer_hash": "...",
  "vocab_size": 262144,
  "vocab_contract_path": "vocab_contract.json"
}
```

The student should reject incompatible vocabulary/tokenizer contracts before initializing training.

### 4.3 Targets section

Representative fields:

```json
{
  "target_type": "corridor_exemplar_v1",
  "dtype": "float32",
  "num_examples": 100000,
  "sequence_length": 128,
  "shard_count": 98,
  "target_params": {}
}
```

The exact shard count depends on configured shard size and corpus size.

### 4.4 Contents section

`contents` is a list of content entries:

```json
{
  "path": "metadata.json",
  "role": "target_store_metadata",
  "sha256": "...",
  "size_bytes": 1234
}
```

The cover page lists required core files and target shards with:

- relative path;
- semantic role;
- SHA-256;
- byte size.

The cover-page validator checks that:

- required paths exist;
- listed sizes match;
- listed hashes match;
- paths do not escape the artifact root;
- validation status agrees with `validation_report.json`.

### 4.5 Validation section

Representative fields:

```json
{
  "status": "pass",
  "validated_by": "radjax_tome.builder.validate_teacher_textbook",
  "validation_report_path": "validation_report.json"
}
```

A student consumer should normally require `status == "pass"`.

### 4.6 Corpus and teacher provenance

When present, the cover page also exposes summaries of:

- corpus provenance;
- teacher model provenance;
- model revision/source;
- tokenizer hash;
- weights/config/directory hashes;
- whether network access was used;
- local-files-only and allow-download settings.

### 4.7 Claims not made

This section exists to prevent overclaiming. Treat it as documentation of what the artifact does **not** prove, such as dense-logit equivalence, student quality, or performance parity.

---

## 5. Core metadata and provenance files

### 5.1 `metadata.json`

This is the target-store metadata used to open the shard store.

Important fields include:

```text
model_id
model_family
target_type
dtype
num_examples
sequence_length
shard_count
target_params
```

`target_params` may include strings describing:

- streaming build status;
- shard size;
- resume support;
- corridor stat support depth;
- dynamic top-k controls;
- corpus lineage;
- teacher lineage.

The student should parse known fields and preserve unknown fields for forward compatibility.

### 5.2 `vocab_contract.json`

This is the authoritative tokenizer/vocabulary contract.

The student should use it to validate at least:

- tokenizer identity;
- tokenizer hash;
- vocabulary size;
- special-token expectations, when present.

Never infer vocabulary compatibility solely from the teacher model name.

### 5.3 `teacher_manifest.json`

This records producer-side details such as:

- artifact type;
- teacher backend;
- creation time;
- local-files-only behavior;
- teacher-model provenance;
- corpus provenance;
- vocab-contract path;
- streaming/resume metadata.

This file is useful for auditability and reproducibility. Student training should not need to understand every producer implementation detail.

### 5.4 `emission_config.json`

This records the effective teacher emission settings.

Important current fields may include:

```text
top_k
num_buckets
dynamic_top_k_min
dynamic_top_k_max
dynamic_mass_threshold
corridor_stat_top_k
min_corridor_stat_top_k
```

Important distinction:

```text
corridor_stat_top_k
```

is the internal support depth used to compute real `top32_mass` and `tail_mass`. It must be at least 32.

```text
dynamic_top_k_max
```

is the cap for retained selected exemplar detail. It is not the corridor mode count and is not the corridor-stat support depth.

---

## 6. Target shards

The `shards/` directory contains compressed NumPy shard files:

```text
shards/shard-00000.npz
shards/shard-00001.npz
...
```

For the current corridor/exemplar score-pass artifact, retained arrays may include:

```text
input_ids
attention_mask
corridor_lengths
corridor_top_token_ids
corridor_confidence
corridor_entropy
corridor_teacher_entropy
corridor_top1_margin
corridor_top8_mass
corridor_top32_mass
corridor_tail_mass
score_example_ids
score_lengths
score_selected_position
score_selected_position_entropy
score_confidence_at_selected_position
score_max_entropy
score_mean_entropy
score_top_token_id
score_source_policy_ids
```

Path A may temporarily capture richer exemplar-source arrays during generation, but a completed selected-only artifact should not retain unselected exemplar payload arrays.

The student corridor loader does **not** need to train directly from these score-pass shards if it consumes the normalized packed mode assignments and mode table. Treat the raw shard arrays as producer data and diagnostics unless the consumer contract explicitly calls for them.

---

## 7. Corridor files

### 7.1 `corridors/corridor_summary.json`

This is the high-level corridor summary.

Representative current fields:

```json
{
  "corridor_artifact_built": true,
  "corridor_modes_built": true,
  "corridor_observation_basis": "full_token_position_corridor",
  "degraded_corridor_export": false,
  "corridor_positions_available": 128000,
  "corridor_positions_used": 128000,
  "corridor_observation_count": 128000,

  "corridor_mode_policy": "stat_bands_v0",
  "corridor_max_modes": 256,
  "mode_count": 47,

  "corridor_stat_top_k": 32,
  "min_corridor_stat_top_k": 32,
  "corridor_tracked_stats": [
    "entropy",
    "top1_margin",
    "top8_mass",
    "top32_mass",
    "tail_mass"
  ],

  "corridor_assignment_storage_kind": "packed_numpy_v1",
  "corridor_assignment_count": 128000,

  "fingerprint_count": 34802,
  "selected_exemplar_count": 64,
  "selected_exemplars_linked_to_corridor_modes": true,
  "non_selected_exemplar_payload_retained": false
}
```

Consumer requirements:

```text
corridor_observation_basis == full_token_position_corridor
degraded_corridor_export == false
corridor_mode_policy == stat_bands_v0
corridor_stat_top_k >= 32
corridor_assignment_storage_kind == packed_numpy_v1
corridor_assignment_count == corridor_positions_used
selected_exemplars_linked_to_corridor_modes == true
```

Do not hard-code an expected `mode_count`. A particular run may discover 47 modes, another may discover a different number. The contract only requires valid artifact-local modes within the configured maximum.

### 7.2 `corridors/corridor_summary.txt`

Human-readable summary only.

Useful for operators, logs, and quick inspection. Do not parse this file in student code.

### 7.3 `corridors/corridor_modes.json`

This is the training-critical corridor mode table.

Top-level structure:

```json
{
  "schema_version": "corridor_modes_v2",
  "mode_policy": "stat_bands_v0",
  "corridor_mode_policy": "stat_bands_v0",
  "corridor_max_modes": 256,
  "corridor_stat_top_k": 32,
  "min_corridor_stat_top_k": 32,
  "tracked_stats": [
    "entropy",
    "top1_margin",
    "top8_mass",
    "top32_mass",
    "tail_mass"
  ],
  "mode_count": 47,
  "modes": []
}
```

Representative mode:

```json
{
  "mode_id": 0,
  "name": "stat_bands_v0/e0_m0_t2",
  "description": "stat_bands_v0 teacher-side corridor mode.",
  "mode_key": {
    "entropy_bin": 0,
    "top1_margin_bin": 0,
    "top32_mass_bin": 2
  },
  "record_count": 35,
  "count": 35,
  "share": 0.0002734375,
  "bounds": {
    "entropy": {"min": 0.0, "max": 0.8, "mean": 0.4},
    "top1_margin": {"min": 0.0, "max": 0.05, "mean": 0.02},
    "top8_mass": {"min": 0.2, "max": 0.5, "mean": 0.33},
    "top32_mass": {"min": 0.5, "max": 0.75, "mean": 0.62},
    "tail_mass": {"min": 0.25, "max": 0.5, "mean": 0.38}
  },
  "representative_examples": [
    {"example_id": "corpus_000000123", "position": 42}
  ],
  "mode_policy": "stat_bands_v0"
}
```

The numeric values above are illustrative; always read actual artifact values.

The student should build an in-memory or device-resident lookup:

```text
mode_id -> five lower bounds + five upper bounds
```

Means are useful diagnostics but are not required for the base corridor hinge loss.

### 7.4 Mode discovery bins

Current default bins are equivalent to:

```text
entropy:
  [0.0, 1.0, 2.5, 4.0, 8.0, +inf]

top1 margin:
  [0.0, 0.05, 0.15, 0.35, 1.0, +inf]

top32 mass:
  [0.0, 0.5, 0.75, 0.9, 1.0, +inf]
```

This gives at most 125 natural combinations with current defaults, while the configured safety cap is 256.

The student does not need to rediscover modes. It consumes the emitted mode table and assignments.

### 7.5 `corridors/mode_assignments.json`

This is a small manifest for packed assignment arrays.

Representative structure:

```json
{
  "schema_version": "corridor_mode_assignments_v3",
  "assignment_policy": "full_token_position_stat_bands_v0",
  "storage_kind": "packed_numpy_v1",
  "corridor_observation_basis": "full_token_position_corridor",
  "full_assignment_retained": true,
  "num_assignments": 128000,
  "num_examples": 1000,
  "arrays": {
    "position_example_index": {
      "path": "corridors/mode_assignments/position_example_index.npy",
      "dtype": "int32",
      "shape": [128000]
    },
    "position": {
      "path": "corridors/mode_assignments/position.npy",
      "dtype": "int32",
      "shape": [128000]
    },
    "mode_id": {
      "path": "corridors/mode_assignments/mode_id.npy",
      "dtype": "int32",
      "shape": [128000]
    },
    "weight": {
      "path": "corridors/mode_assignments/weight.npy",
      "dtype": "float32",
      "shape": [128000]
    },
    "fingerprint_index": {
      "path": "corridors/mode_assignments/fingerprint_index.npy",
      "dtype": "int32",
      "shape": [128000]
    }
  },
  "examples_metadata": {
    "path": "corridors/mode_assignments/examples_metadata.jsonl",
    "num_examples": 1000
  }
}
```

Training-critical arrays:

```text
position_example_index.npy
position.npy
mode_id.npy
weight.npy
```

Diagnostic-only array:

```text
fingerprint_index.npy
```

### 7.6 Packed assignment semantics

For assignment row `i`:

```python
example_index = position_example_index[i]
position = position[i]
mode_id = mode_id[i]
weight = weight[i]
```

`example_index` points into `examples_metadata.jsonl`.

Representative metadata line:

```json
{"example_index": 0, "example_id": "corpus_000000000"}
```

The student then resolves the source input IDs for that example through the artifact’s example/shard data or a normalized consumer index.

Validation requirements include:

- all arrays exist;
- dtypes match manifest;
- all shapes equal `num_assignments`;
- `position_example_index` is in range;
- positions are nonnegative and valid for sequence length;
- every `mode_id` exists in `corridor_modes.json`;
- weights are finite and nonnegative.

### 7.7 `corridors/corridor_fingerprints.json`

This is a **diagnostic artifact**, not the base corridor training target.

Current diagnostic fingerprints may group observations using details such as:

- top token ID;
- entropy bucket;
- confidence bucket;
- relative position bucket.

Fingerprint count may be much larger than corridor mode count.

Example:

```text
34,802 diagnostic fingerprints
47 stat-band corridor modes
```

Do not confuse fingerprints with modes.

Student corridor training should use:

```text
mode_id + mode bounds
```

not `fingerprint_id`.

---

## 8. Selected exemplar files

### 8.1 `leaderboards/selected_exemplars.json`

This is the selected-exemplar index/selection record.

Representative top-level structure:

```json
{
  "schema_version": "selected_exemplars_v1",
  "created_at": "...",
  "delivery_path": "two_pass_rerun_selected",
  "score_policy": "entropy_top_n_v1",
  "selected_exemplars": []
}
```

The entries identify which examples/positions were selected and contain selection/linkage metadata.

This is not necessarily the full payload used for exemplar loss.

### 8.2 `selected_exemplars/selected-exemplars-00000.json`

This is the full selected exemplar payload shard.

Representative structure:

```json
{
  "schema_version": "selected_exemplar_payload_shard_v1",
  "delivery_path": "two_pass_rerun_selected",
  "selected_exemplars": []
}
```

Required selected payload fields currently include:

```text
selected_example_id
selected_position
selected_score
selected_policy
source_delivery_path

top_token_ids
top_log_probs
top_probs
top_selection_mask
effective_top_k

top_mass
tail_mass
bucket_masses
teacher_entropy

sequence_length
vocab_size
num_buckets
dynamic_top_k

corridor_mode_id
corridor_fingerprint_id
corridor_assignment_status
```

Representative entry:

```json
{
  "selected_example_id": "corpus_000000528",
  "selected_position": 91,
  "selected_score": 8.125,
  "selected_policy": "entropy_top_n_v1",
  "source_delivery_path": "two_pass_rerun_selected",

  "top_token_ids": [123, 456, 789],
  "top_log_probs": [-2.0, -2.2, -2.5],
  "top_probs": [0.135, 0.111, 0.082],
  "top_selection_mask": [true, true, true],
  "effective_top_k": 64,

  "top_mass": 0.72,
  "tail_mass": 0.28,
  "bucket_masses": [0.1, 0.08, 0.06, 0.04],
  "teacher_entropy": 8.125,

  "sequence_length": 128,
  "vocab_size": 262144,
  "num_buckets": 4,
  "dynamic_top_k": true,

  "corridor_mode_id": 46,
  "corridor_fingerprint_id": "fp_002030",
  "corridor_assignment_status": "linked"
}
```

Values above are illustrative.

### 8.3 Dynamic top-k semantics

`effective_top_k` may differ per exemplar.

The student must not assume:

```text
effective_top_k == 32
effective_top_k == dynamic_top_k_max
all rows have equal valid K
```

Use `top_selection_mask` and/or `effective_top_k` to mask padded entries.

### 8.4 Exemplar delivery paths

The artifact may report one of:

```text
one_pass_pruned_candidate
two_pass_rerun_selected
```

These are producer implementation paths.

If parity has been validated, student semantics should be equivalent:

- same selected example IDs;
- same selected positions;
- same selection ranks;
- same corridor mode links;
- compatible selected payload shapes.

The student should not change its loss based on delivery path.

---

## 9. Reports

### 9.1 `validation_report.json`

Machine-readable artifact validation.

The student should require a passing report unless explicitly testing malformed artifacts.

### 9.2 `production_build_report.json`

Top-level producer report containing:

- build status;
- validation status;
- selected delivery path;
- counts;
- configured dynamic top-k controls;
- corridor summary fields;
- warnings and blockers;
- timing information, when enabled.

Useful for audit and launch tooling. Avoid making the training loop depend on report-only fields when the semantic files already contain them.

### 9.3 `delivery_report.json`

Selected-exemplar delivery report.

Important fields include:

```text
num_examples_scored
num_positions_scored
num_selected_exemplars
selected_example_count
teacher_rerun_count
selected_payload_source
selected_payload_shard_count
selected_exemplar_payload_retained
non_selected_exemplar_payload_retained
corridor_mode_policy
corridor_mode_count
corridor_assignment_storage_kind
selected_exemplars_linked_to_corridor_modes
```

### 9.4 `production_progress.json`

Operational sidecar updated during long builds.

Possible phases include:

```text
score_pass
selected_rerun
corridor_export
validation
report_writing
complete
```

This file is for operators. Student training should not require it.

### 9.5 `run_manifest.json`

Streaming-build operational state and resume information.

This is producer infrastructure, not a student training target.

---

## 10. Corridor loss expected on the student side

For a student statistic `x` and inclusive corridor `[lo, hi]`:

```python
below = relu(lo - x)
above = relu(x - hi)
penalty = below**2 + above**2
```

Therefore:

```text
inside corridor -> zero penalty
below lower bound -> squared distance to lower bound
above upper bound -> squared distance to upper bound
```

The student should compute its own five statistics at assigned positions:

```text
entropy
top1_margin
top8_mass
top32_mass
tail_mass
```

Then apply configured stat weights and per-record `weight`.

Useful diagnostics:

```text
inside_entropy_rate
inside_top1_margin_rate
inside_top8_mass_rate
inside_top32_mass_rate
inside_tail_mass_rate
inside_all_rate
```

A scientifically useful corridor should produce nonzero loss/gradient for at least some random or untrained student states.

---

## 11. Suggested student-side adapter API

Keep all artifact-file knowledge inside one consumer package.

Recommended conceptual boundary:

```text
Tome directory
    ↓
TomeArtifactReader
    ↓
Normalized corridor and exemplar batches
    ↓
Student trainer
```

Suggested normalized types:

```python
@dataclass
class TomeIdentity:
    tome_version: int
    teacher_model_id: str
    tokenizer_id: str
    tokenizer_hash: str
    vocab_size: int
    sequence_length: int
    target_type: str


@dataclass
class CorridorModeTable:
    mode_ids: Array
    entropy_min: Array
    entropy_max: Array
    top1_margin_min: Array
    top1_margin_max: Array
    top8_mass_min: Array
    top8_mass_max: Array
    top32_mass_min: Array
    top32_mass_max: Array
    tail_mass_min: Array
    tail_mass_max: Array


@dataclass
class CorridorBatch:
    input_ids: Array
    positions: Array
    mode_ids: Array
    weights: Array


@dataclass
class ExemplarBatch:
    input_ids: Array
    positions: Array
    top_token_ids: Array
    top_log_probs: Array
    top_probs: Array
    top_selection_mask: Array
    effective_top_k: Array
    bucket_masses: Array
    top_mass: Array
    tail_mass: Array
    teacher_entropy: Array
    corridor_mode_ids: Array
```

The training core should not open JSON/NPY/NPZ paths directly.

---

## 12. Required consumer validation

Before training, the student should reject the artifact if any of these fail.

### Identity

```text
artifact_kind == radjax_tome
supported tome_version
layout == unpacked_directory
cover-page hashes and sizes validate
validation status == pass
```

### Token/vocab contract

```text
tokenizer ID/hash compatible
student vocab size compatible
all token IDs in range
student sequence capability >= artifact sequence length
```

### Corridor contract

```text
target_type supports corridor training
mode policy == stat_bands_v0
tracked stats exactly recognized
corridor_stat_top_k >= 32
assignment storage kind supported
assignment counts/shapes consistent
all mode IDs valid
all bounds finite
min <= mean <= max
weights finite and nonnegative
```

### Exemplar contract

```text
selected payload schema supported
all selected positions valid
top arrays have compatible shapes
effective_top_k in valid range
selection mask agrees with effective_top_k
probabilities/log-probabilities finite
tail/top/bucket masses finite
corridor assignment status == linked
corridor_mode_id exists
```

---

## 13. What not to hard-code

Do not hard-code:

```text
mode_count
fingerprint_count
specific mode IDs
specific fingerprint IDs
selected exemplar count
effective_top_k
dynamic_top_k_max
number of shards
delivery path
artifact absolute paths
```

Do not assume mode IDs are stable across artifacts.

Do not treat diagnostic fingerprints as the corridor loss target.

Do not parse the human summary as a contract.

---

## 14. Stability boundary

### Considered stable enough for student development

```text
cover sheet as entry point
tokenizer/vocab provenance
corridor tracked statistics
stat_bands_v0 mode table
packed position -> mode assignments
artifact-local mode IDs
selected exemplar payload semantics
corridor and exemplar as distinct passes
```

### May still evolve without changing student semantics

```text
extra report fields
progress reporting
diagnostic fingerprint format
additional provenance
number of selected payload shards
compression/container format
additional optional arrays
schema minor versions with adapters
```

The student should isolate those details behind the reader/adapter layer.

---

## 15. Recommended golden contract fixture

The two repositories should share or reproduce a tiny golden Tome fixture containing:

```text
8–32 source examples
multiple stat-band modes
packed assignments
at least several selected exemplars
dynamic top-k values
valid cover-page hashes
passing validation report
```

Student CI should prove:

1. cover page validates;
2. vocabulary contract loads;
3. all packed assignment arrays load;
4. every assignment resolves a valid mode;
5. corridor batches can be formed;
6. corridor loss is finite;
7. exemplar batches can be formed;
8. dynamic top-k masking works;
9. incompatible vocab/sequence contracts fail loudly.

---

## 16. Minimal student implementation order

1. Implement `TomeArtifactReader`.
2. Validate `cover_page.json`.
3. Load vocabulary and sequence contract.
4. Load `corridor_modes.json`.
5. Load packed mode assignments.
6. Resolve assignment rows to source `input_ids`.
7. Emit normalized `CorridorBatch`.
8. Implement the five distribution statistics.
9. Implement squared-hinge corridor loss.
10. Load selected exemplar payload shards.
11. Emit normalized `ExemplarBatch`.
12. Implement standalone exemplar loss/pass.
13. Add sequential corridor -> exemplar checkpoint flow.

---

## 17. Final mental model

A Tome is not just “teacher logits in a folder.”

It is:

```text
identity + provenance
source-conditioned corridor assignments
coarse teacher-derived behavioral bounds
a small sharp exemplar reservoir
validation and integrity metadata
```

The corridor side says:

```text
Given this input and this token position,
keep these five distribution statistics inside this behavioral envelope.
```

The exemplar side says:

```text
At this selected interesting position,
imitate this sharper compressed slice of the teacher distribution.
```

That is the student-facing contract.
