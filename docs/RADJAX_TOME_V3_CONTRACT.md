# RADJAX-Tome v3 Portable Contract

RADJAX-Contract 0.2.0 packages the released implementation-neutral
`radjax_tome_artifact_contract` v1 assets. They are static data and do not
import RADJAX-Tome or alter existing v2 Contract APIs.

Use `radjax_contract.tome.tome_contract_root()` to locate the installed asset
tree and `tome_contract_asset_path()` to open an individual checked-in asset.
The `SHA256SUMS` inventory pins every asset other than itself.

The contract distinguishes producer byte-determinism from consumer safety.
Consumers reject unsafe or corrupt archives; safe noncanonical container
metadata is reportable and strict-mode rejectable. The v3 identity is
independent of profile and transport. Historical v2 and package-v1 inputs
remain explicitly incomplete compatibility descriptors.

The authoritative contract source is this released Contract package. Tome may
retain a byte-verified offline mirror for development and conformance tests,
but cannot independently edit it.
