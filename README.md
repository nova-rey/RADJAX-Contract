# RADJAX-Contract

RADJAX-Contract defines the artifact, vocabulary, manifest, provenance, and
validation contracts shared by RADJAX-Tome and RADJAX-Student.

It does not load teacher models, train students, run JAX kernels, or depend on
PyTorch/Transformers.

This scaffold is intentionally small. Artifact files are the API between Tome
and Student; Python imports between those producer and consumer repos are not.

