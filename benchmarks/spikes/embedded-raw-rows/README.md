# Embedded prepared raw-row trial

**Result: the bounded native-embedded trial passes without changing the embedded
API or adding a MariaDB patch.** Reusing already-serialized binary rows is a
viable candidate for reducing the result conversion adapter. This does not
establish product adoption, WASIX integration, overall native migration or lower
total version-upgrade cost. The main concern is a new dependency on the cached
row representation, whose lifetime and length rules require a small audited
adapter and a per-version check.

## Fixed identities and actual method

- Product/serializer baseline: `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`.
- Final executed trial source_commit: `a424c87cac8523aca96eda3387f461517d30c5d9`.
- MariaDB package: official12.3.3 Ubuntu24.04 arm64 `libmariadbd19` and matching
  development headers. `packages.json` records exact archive URLs/hashes.
- The shared library's SHA256 is
  `42504138ef1495790c872380c028a51d23420e503e183ef6f82d3b832c51d10c`.
  Its embedded revision string is `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`,
  matching the main guest's upstream source_commit. This is a distribution
  binary, not the project's patched/generated guest or an independently rebuilt
  source tree. Existing legacy project patches were not applied to this library.
- Runtime/compiler container image identities are in `images.txt`. Execution
  was Linux arm64; the Go comparison ran macOS arm64/Go1.27.3.

A tiny C adapter calls the existing `mysql_stmt_store_result`, reads
`MYSQL_STMT.result`/`MYSQL_ROWS`, and copies each row before freeing the result.
For each stored row, `length` includes the removed leading0x00 byte: copy exactly
`length-1` bytes from `data`, prefix0x00, and leave packet header/sequence to the
host. No THD/Item_param modification, network endpoint or native controller is
introduced. The code uses pointers only inside the native C process.

The paired path uses the exact baseline `ps_result_bindings`, `ps_cell`,
`ps_columns`, and their dependencies, mechanically extracted from committed
source and the hash-pinned recipe. It uses the real embedded library to fetch
columns. The Go comparator calls the unchanged production
`internal/preparedproto.EncodeBinaryRow` and checks byte equality with the raw
copy from the same execution. This checks the row payload, not every public
wire packet or full `ps_capture_result`/host lifecycle integration.

A second fresh statement on the same MYSQL connection executes each case
without calling `mysql_stmt_bind_result`/`mysql_stmt_fetch`; its copied raw rows
and type/flag descriptors must match the paired path. Copies are serialized only
after `mysql_stmt_free_result`, so no borrowed row pointer crosses cleanup.
Statement IDs are not substituted and there is no second SQL connection for a
single session. Same-statement repeated execution keeps output buffers alive
until replacement/statement close.

## Observed results

[comparison.json](evidence/comparison.json): **15 result observations per path,
16 compared rows,132241 row-payload bytes; no differences.** A one-byte mutation
is rejected by the equality oracle. This is not an allocation-boundary or ASan
negative test.

- 24-column typed table: signed/unsigned TINYINT/SMALLINT/MEDIUMINT/INT/BIGINT,
FLOAT/DOUBLE, DECIMAL, DATE/DATETIME/TIMESTAMP/TIME, text/binary/BLOB, BIT, YEAR,
GEOMETRY. Includes integer extremes, fractions, negative838-hour TIME,
Unicode/zero bytes and NULLs across several bitmap bytes.
- Repeated executions of one prepared statement with bound integer values0/1/2;
  result sets contain3/2/1 rows. Empty results are also checked.
- Strings of250/251/65535/65536 bytes, plus temporal midnight and microseconds.
- A session-local temporary table is visible through the same connection;
  an inserted row is observed in a transaction and absent after rollback.
- Duplicate-key error1062 is observed, the failing statement is reset/closed,
  and a subsequent statement succeeds. Recovery/re-execution of that same
  failed statement is not claimed.
- A stored procedure yields two row results and a final no-column result.
  Another yields a normal row, an OUT row with native status4106, and a final
  no-column result. Existing host capability filtering is not exercised.

The first compile attempt failed because `EMBEDDED_LIBRARY` was omitted; the
header selected server-prefixed symbols. Defining the intended build mode fixed
linking without changing any header/library. The initial9-result/12-row success
at `8f24e527` is recorded by its full SHA in
`evidence/attempt2-candidate-identity.json`; the final run adds chain/OUT coverage.
An io_uring restriction caused the official engine to use its libaio fallback;
it did not prevent either run. All initial/final logs are retained.

## Meaning for #65

The existing Go input/handshake/capability/statement-owner machinery can stay.
The result-side column decode → custom cell encoding → Go row encoding can
potentially shrink to a cached-row copy. In this experiment that read-only
adapter is `copy_raw` in `probe.c`; the remainder is fixture/comparison scaffolding.
No server NET/Protocol coexistence, prepared input conversion rollback or new
Vio/controller is needed for this limited operation.

It does **not** eliminate the existing legacy prepared metadata/TIME patches,
replace text output or metadata/OK/ERR serializers, or remove JSON/hex by itself.
Results are still buffered. Memory/latency/CPU gains, metadata shape changes,
allocation failures, maximum-packet boundaries, every supported type/value,
WASIX/wasm2go and public Snapshot/Fork/stop semantics remain unverified.
Public C functions are unchanged, but cached-row layout is not a promised stable
raw-row API. Reading a field exposed in a header still creates an upgrade check.

Recommendation: if the Human wants the next slice, integrate only this result
representation into an experimental legacy guest/host pair and compare the
existing prepared output/chain/capability/cleanup oracles. Before building,
review the exact internal-envelope change and source/length/lifetime dependency.
Do not resume the broad native campaign or drop existing guarantees to make
this adapter pass. #150 remains independent.

## Reproduction and cleanup

Use a clean checkout of the trial ref and a new experiment-workspace with
`--min-free-gib 12 --budget-gib 6`; the run is bounded to900 seconds. Run
`scripts/git_identity.py inspect HEAD` first. `run.sh` expects workspace runner
variables `MARIAMEM_EXPERIMENT_TEMP` and `MARIAMEM_EXPERIMENT_EVIDENCE` and fresh
`temp/datadir`. It obtains fixed-hash packages/recipe with `acquire.py`, extracts
the existing serializers, compiles the C harness and initializes a private data
directory. Runtime and compilation containers use `--network none`.

The recorded builder image was already installed. A clean machine does not need
that local image or a WASIX SDK: build `Dockerfile.builder` in this directory and
set `RAW_ROWS_BUILDER` to its resulting image ID. This smaller compiler-image
recipe is provided but was not run in this trial. Record the new compiler/image
identity; byte-for-byte compiler/binary reproduction is not claimed. The runtime
image has a public digest in `run.sh`. The trial requires Linux arm64 containers.

For a fresh workspace use `experiment_workspace.py run --timeout 900`. After a
failed run, that helper deliberately refuses a second run in the same workspace;
this trial used the documented manual `experiment_disk.py` guard with the same
6GiB/free12GiB/900-second limits, then finalized manually. Never edit the receipt
to pretend a failed run was fresh or successful.

To recheck saved observations without a database, decompress
`evidence/rows.jsonl.gz` to a temporary file and run
`go run ./benchmarks/spikes/embedded-raw-rows/compare <file>` from the repository.
Full data is compressed, not omitted; `observations.json` supplies compact row
hashes/status/types. All evidence hashes are in `SHA256SUMS.json`.

Downloads, extracted headers/library, native executable, database files and Go
cache are disposable; no user data or other experiment trees are part of cleanup.
The root checkout's pre-existing changes remain untouched.
