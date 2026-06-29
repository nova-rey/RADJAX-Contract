# Split Integrity

`validate_three_way_split` rejects train, calibration, and final-test manifests
that overlap by:

- `example_id`
- `token_sequence_hash`
- `source_text_hash`

This protects calibration and final-test measurements from accidental leakage.

