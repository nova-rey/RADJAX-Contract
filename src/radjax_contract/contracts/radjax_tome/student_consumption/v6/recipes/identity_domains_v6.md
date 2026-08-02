# V6 identity domains

`raw_sha256` binds exact physical bytes. Resource semantic identities bind a
canonical logical projection. `behavioral_authority_digest` binds only the V5
language binding, behavioral source, authority registry, joins, and fixed
selection authority. `composition_digest` additionally binds the delivery
registry and exact package identity. Therefore equivalent behavior may have a
different composition digest; exact-package replay may not substitute it.
