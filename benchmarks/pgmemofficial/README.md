# pgmem official-method adaptation for mariamem A/B

Method: shibukawa/pgmem `bench/alternatives/main.go`, `pgmem.go`, and root
`pgmem_test.go` at a61005d37d01e6671f814fe8ca828222e8147df4. The original files and
hashes are retained with results; upstream MIT license is UPSTREAM-LICENSE.
This is a MariaDB adaptation for old/new mariamem, not a run of PostgreSQL/pgmem,
not the separate50-read/20-write parallel modelcase, and not a Docker/devbox or
cross-machine comparison with the public benchmark numbers.

Use the same1000 indexed bench rows,1000 users/10000 orders,300 indexed warmups,
3000 indexed lookups per TCP/Pipe path,200000 MD5 rows sorted, one excluded heavy
warmup plus3 heavy queries, and20 serial Fork→JOIN count→connection drain/Close
cycles. Five alternating old/new fresh-process pairs are measured. Each has a
small excluded pilot beforehand. Startup is library Start→TCP SELECT1; process
launch and package init are excluded. Snapshot is separately recorded, and Fork
includes server initialization rather than being only a data-directory clone.
Source Snapshot consumes its DB under mariamem's existing contract.

Dialect adaptations: MySQL driver1.9.3 with explicit statement preparation to
match pgx's prepared-cache usage, and Config.DialFunc for in-process wire;
BIGINT AUTO_INCREMENT, VARCHAR255 unique email and TIMESTAMP defaults;
generate_series becomes an exact cartesian product of tiny derived digit tables.
The resulting row cardinalities and indexed MD5 values are checked. Physical seed
ordering/implicit ID assignment are not claimed identical across engine dialects.
An explicit LIMIT200000 keeps the derived ORDER BY from being optimized away;
both plans must contain filesort and return200000. These changes affect absolute
cost, so only the identical MariaDB workload's old/new differences are compared.
The server/default buffer pool remains unchanged (16MiB, not pgmem's32MiB).

INSERT is an extra control, not an upstream standalone measurement.1000 monotonic
single-row inserts per text/autocommit, prepared/autocommit and prepared/one-tx
mode; prepare/one row warmup are excluded, transaction Begin/Commit included.
Every affected-row count, final count, sum of IDs and total value length must match.
Simple-query warmup/representative MD5 values and all timed widths are checked;
this is not a full-value validation of every timed SELECT. Per-query heavy result
and all seeded/isolated counts are checked. RSS is this process's absolute ps RSS,
not upstream phys_footprint growth or a peak/backend-only measure.

Build this standalone benchmark module twice, each with a go.mod replacement to
a clean source checkout of the chosen mariamem commit. Use Go1.26.10, CGO0,
`go build -p1 -trimpath -buildvcs=false`, and source/harness linker labels as in
inputs.json. The explicit pre-build git_identity receipt and clean check establish
the library source; labels alone do not. Record the actual replacement module,
checksum inputs and binary hash. Only main.go is shared; production code is not
overlaid or edited. Example invocation after build: `bench -output result.json`.
This uses the official counts above. Pilot flags reduce counts and are not included
in the measured summaries. Never run compilation/heavy benchmarks during timing.
