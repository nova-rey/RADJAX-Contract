# Native-v3 Student consumption v4

`native_v3_student_v4` supersedes v3 for new Tome production. It preserves
v3's required delivery receipt and authority-reference resources as closed,
raw-integrity-bound validation evidence. The resolver validates both bodies
and their cross-resource constraints before returning a descriptor.

The v4 consumption semantic identity contains only batch-semantic resource
declarations: every required resource except `delivery_receipt` and
`authority_reference`. Their raw inventory digests and manifest entries remain
mandatory, but their body semantic digests do not contribute to the batch
identity. Therefore equivalent Path A and Path B payloads have the same v4
consumption digest even when they retain distinct production evidence.

This is an additive profile, not a reinterpretation of v3. Consumers must
negotiate `native_v3_student_v4` explicitly; they must not fall back to v3 or
v2. V2 and v3 remain available for their published historical artifacts.
