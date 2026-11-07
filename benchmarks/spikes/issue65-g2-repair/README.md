# G2 native prepared repair

Human continuation after CI42330785223: repair the observed type/LONG_DATA gaps.
The Human explicitly chose to preserve upstream NULL fallback for BIT,GEOMETRY,
INT24,YEAR. Original G1/G2 oracles remain fixed;short handshake stays a visible
contract difference. No canonical guest/host integration or release.

Pinned upstream83e909fc sql_type.cc:8226 Type_handler::Item_param_set_param_func
sets NULL without advancing the packet. The four observed type handlers inherit
that fallback. The G1 exact-consumption check converted that upstream behavior
into1835. Preserve the native fallback without adding a decoder:only a non-NULL
parameter actually visiting one of these four handlers exempts the remaining
bytes from the added end check. This also preserves upstream cursor behavior in
mixed bindings;it is not a promise that those types decode their sent values.

Validate all fresh descriptors using the upstream type sanity predicate before
entering execute_loop,so rejection leaves pending LONG_DATA and conversion state
untouched. In both logged/nonlogged insertion paths,report native LONG_DATA type
mismatch as1210 before the existing generic malformed-packet remapping. Preserve
ordinary malformed-value1835,ordinary strict surplus rejection and D2.

Budget:one native guest build,one local regression execution and at most one
Linux CI for this repair;active2h,owned workspaces12GiB each,free floor12GiB.
The existing full G1 baseline and unchanged241 G2 observations are the runtime
regression checks. Short-handshake mismatch is expected to remain NOT_READY.
Until new guest/binding/runtime evidence exists,this is an unverified candidate.
