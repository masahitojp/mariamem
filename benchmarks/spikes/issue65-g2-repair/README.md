# G2 native prepared repair

Human continuation after CI42330785223: repair the observed type/LONG_DATA gaps.
The Human explicitly chose to preserve upstream NULL fallback for BIT,GEOMETRY,
INT24,YEAR. Original G1/G2 oracles remain fixed;short handshake stays a visible
contract difference. No canonical guest/host integration or release.

Pinned upstream83e909fc sql_type.cc:8226 Type_handler::Item_param_set_param_func
sets NULL without advancing the packet. BIT,INT24,YEAR inherit that fallback;GEOMETRY explicitly performs the same
NULL operation in sql_type_geom.cc:680. The G1 exact-consumption check converted that upstream behavior
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

The actual prepared source is SHA-pinned and compiled in a small C++ harness
with dependency stubs in [check_source.py](check_source.py). It checks descriptor
preflight(including an invalid second descriptor),the four NULL fallbacks,
bitmap-NULL surplus rejection,ordinary strict surplus and1210 in logged and
nonlogged insertion paths. This source-seam check is not an engine qualification.
The CI builder runs it immediately after source preparation and before the
unchanged build script disposes that source. The G1 patch-text guard now accounts
for added/removed lines when checking the replacement end condition;its runtime
oracles remain unchanged.

[Platform comparison](compare_results.py) retains every expected/actual/pass field
except the named mid-output drain byte count already observed to vary with
scheduling. It validates that quantity's integer schema and never changes the
contract readiness result. Missing/duplicate rows,another actual difference,
changed expectations/pass outcomes or a different guest cannot match.
