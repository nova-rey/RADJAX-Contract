# P1.5 Production Tome Alignment Receipt

**Status:** pass  
**Receipt version:** 1  
**Handoff version:** 1.1

## Immutable Inputs

- RADJAX-Tome: `fe5d51e769627cd89124fbb51dbdad2f80ad2fab`
- RADJAX-Contract implementation:
  `cbce741f7c4c14f6716207e5838bf152cce73e49`
- RADJAX-Student baseline:
  `7709e5e6dbba569046addaec625a707278441d5f`

## Shared Fixture

- Fixture ID: `production_multi_surface_v1`
- Fixture schema: `production_tome_fixture_v1`
- Artifact tree digest:
  `468a259d518a28a6f60af8c339b124b65fd52da0640544d186eb9609933608d1`
- Cover page: version 2
- Tome: version 1
- Surface schema: `behavioral_surface_v1`
- Pass-plan schema: `recommended_training_plan_v1`

The producer recipe regenerates the packaged artifact byte for byte. Contract's
wheel contains all 23 fixture files, including packed NumPy arrays and the target
shard.

## Verification

| Repository | Gate | Result |
| --- | --- | --- |
| RADJAX-Tome | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q` | 425 passed, 22 skipped |
| RADJAX-Tome | `python3 -m ruff check .` | pass |
| RADJAX-Contract | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q` | 83 passed |
| RADJAX-Contract | `python3 -m ruff check .` | pass |
| RADJAX-Student | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q` | 18 passed |
| Cross-repository | fresh fixture generation and recursive diff | byte-identical artifact |
| RADJAX-Contract | wheel package-data inspection | all 23 fixture files present |

Blockers: none. Warnings: none.

## Claims Not Made

This receipt does not claim model quality, network verification, Student
training, Student P1.1/P1.2 correction, corridor or exemplar loaders, or quality
parity between producer delivery paths.

## Phase Status

```text
P1.5  Tome/Contract production alignment   COMPLETE
P1.6  Student artifact-view correction      UNBLOCKED
P1.7  Student run-defaults correction       BLOCKED ON P1.6
```
