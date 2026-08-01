# Canonical JSON and JSONL v1

Semantic JSON is UTF-8 without BOM, rejects duplicate keys and nonfinite
numbers, and is encoded with lexicographically sorted keys and compact
separators. JSONL is one JSON object per LF-terminated line; CRLF, blank lines,
and duplicate keys are rejected. Semantic floats are finite; negative zero is
normalized to positive zero where zero is allowed.

The consumption semantic digest is `sha256:` plus SHA-256 of the canonical
semantic-identity payload without its `semantic_digest` member.
