# Vocab Contract

`VocabContract` binds tokenizer identity, vocabulary size, optional tokenizer
hash, model identity, model family, and special token IDs.

Two contracts are compatible when tokenizer identity and vocabulary size match,
and when both hashes are present they are equal.

