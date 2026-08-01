# NPZ Semantic Hash v1

NPZ members sort by UTF-8 member name. For each member, hash a length-framed
record containing its name, declared dtype, rank, dimensions, declared axes,
and canonical little-endian C-order value bytes. Frame all text and byte
segments with unsigned 64-bit little-endian lengths. Object arrays, duplicate
members, noncanonical dtype declarations, and undeclared members are invalid.
Raw inventory SHA-256 remains the byte-integrity check for the original NPZ.
