# Archive Safety v1

Validated resource opening permits at most 100,000 members, 64 GiB per member,
1 TiB total uncompressed bytes, and a 10,000:1 compression ratio. Paths must
be normalized relative POSIX paths. Duplicate names, links, device files, and
other special members are rejected. `strict=false` can report only documented
safe noncanonical transport; it never relaxes these limits or semantic checks.
