# lite4mariadb settings inventory and bounded-default control

**Conclusion:** removing six lightweight-profile overrides does not establish a consistent performance improvement or resolve the long SQL waits. The bounded-default profile still has about400ms SQL spans. Do not adopt the profile or infer that a particular setting is the cause. This finite experiment is complete; no parameter sweep follows automatically.

[Inventory](inventory.json) · [Graph](report.html) · [All20 primary processes](processes.csv) · [Summary](summary.json) · [Effective values](effective-current.json) / [bounded default](effective-bounded-default.json)

## What “default” means here

Same embedded/WASIX MariaDB12.3.3 build and adopted UCA source. **B is a constrained default-like profile, not all upstream defaults, not a native MariaDB server, and not stock SQL semantics qualification.** All25 original argv entries (program plus24 options) are inventoried. Six optional overrides are omitted;19 entries remain. SQL checks confirm exactly six variable differences in root and children.

| Setting | Current request | Current effective | B effective after omission |
|---|---|---|---|
| innodb_read_io_threads |1|1|4|
| innodb_write_io_threads |1|2|4|
| innodb_purge_threads |1|1|4|
| max_connections |10|10|151|
| table_open_cache |32|32|2000|
| thread_cache_size |0|0|151|

The source default for thread cache is256, but startup caps it to max_connections (pinned mysqld.cc:9490–9491). The initial metadata assertion expected256 and stopped before any primary measurement. The failed attempt is retained; expected effective value was corrected to min(256,max_connections), one new B preflight passed, and the profile/primary plan were unchanged. This is not a failed performance run silently relabelled PASS.

Retained bounds: buffer pool size/max16MiB and log buffer2MiB in both arms. Pinned declarations give upstream buffer pool128MiB and log buffer16MiB; those capacity changes are **not tested here**, so this does not answer #88 or exclude interactions with larger capacities. Native AIO remains OFF; guest paths, skip-networking, skip-grant-tables, binlog setting, explicit InnoDB and prepared auth keypaths remain fixed. Defaults of these retained entries are not exhaustively resolved; inventory.json marks that limitation explicitly.

Additional effective settings shared by A/B: buffer-pool load at startup OFF in fresh root and ON in Fork children; dump at shutdown ON; I/O capacity200/max2000; flush_sync ON; flush_log_at_trx_commit1. The fresh/child distinction is observed, not attributed to a specific source assignment by this inventory. Metadata queries run only in preflight; ordinary timing executes the original workload without those queries.

## Fixed measurement results

One Apple M1/16GiB/macOS27.2; Go1.27.3/CGO0/GOMAXPROCS8/GOGC100. 1,000 integer rows,48 independent children, Pipe, cap=P. P4/P8 each5 fresh-process pairs, rotated P order and alternating profile order; one separate warmup/cell. All samples retained. Batch includes child SQL/retirement/Close, excludes root prep/capture/final Snapshot close. CPU is process user+system across the entire batch. RSS is20ms sampled batch process peak, not retained-child memory. SQL span combines pristine COUNT/SUM, UPDATE and verification SELECT, not an exclusive COUNT measurement.

| P | Profile | Batch median ms | Fork p50 median ms | Batch CPU median ms | Peak RSS median MiB | SQL>100ms /240 | SQL>500ms /240 | Max SQL ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 4 | current | 606.1 | 33.74 | 2927.4 | 362.2 | 0 | 0 | 19.20 |
| 4 | bounded-default | 602.8 | 34.92 | 2820.2 | 367.0 | 1 | 0 | 397.68 |
| 8 | current | 619.5 | 52.08 | 3223.2 | 662.5 | 5 | 1 | 811.65 |
| 8 | bounded-default | 613.0 | 51.68 | 3252.3 | 655.5 | 6 | 0 | 411.17 |

The independent medians above are descriptive; subtracting them is not the median paired effect. Paired medians (positive savings = B faster/lower):

| P | Batch saved | CPU saved | Fork saved | RSS added |
|---|---:|---:|---:|---:|
| 4 | 2.67% | -0.02% | -1.217ms | 4.80MiB |
| 8 | -5.98% | 0.44% | 3.983ms | -6.94MiB |

P8 batch pair effects range from60.1% slower to58.2% faster. No stable general batch speedup follows from the near-equal independent cell medians. B has zero>500ms spans in this finite sample but six>100ms spans at P8, versus five in A. Absence of800ms cases is not proof of a fix or a frequency estimate. P4 B also has a397.68ms span while A has no>100ms span. The shorter-tail/longer-tail mix cannot be assigned to any one of the six changed settings.

## Correctness, provenance and limits

Pinned recipe24be9371a2f6c71250a2356631ad6feab2280b02 / lite4mariadb.c SHA256c0a959b6… verified against guest/input.json; MariaDB source83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e files are separately hashed with exact excerpts. Original25 argc/argv strings are validated before compaction on every startup. Selector unit checks25/19 retained argv/order/null termination, unchanged non-argv/string bytes, and rejection of malformed mode/count/preimage. Early tooling compile/fixture failures are retained separately, before successful build or DB timing.

Measured harness source_commitb399bf6d99bda0dc9bf6c20a783b076a8f1e9cde; product source1862f4a89397bddfa1820d835106d3437a438cf7. Exact clean commit identity checked with scripts/git_identity.py before build. Parent is the earlier observation harness3be0dd9e. One binary runs both arms, switching only host experimental argv selection at process start. Origin guest SHA2566d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe is provenance for the input guest; the argv-overlay variant is **UNQUALIFIED**, not a newly built WASM bearing that hash. No canonical guest/generated code was edited.

Two accepted positive preflights eachcheckroot+8children through SQL, with row/isolation/cleanup checks. Two wrong-seed controls fail as intended and clean up. All20 primary processes and four warmups pass original SQL/pristine baseline/independent update/cleanup oracles, and active-child census matches cap. One preliminary B preflight additionally completed SQL/cleanup but failed the256-vs151 metadata assertion; it remains separate. Its SQL report is retained; sampled RSS rows were not saved before that assertion and are not claimed as retained evidence. Total29 DB process attempts,28 accepted controller records. No primary retry or sample removal. RSS safety bound3GiB and disk budget6GiB/free reserve12GiB were not breached.

No stage trace/profile is enabled in ordinary comparison. This is1host/small fixture, not both-platform acceptance, retained-child RSS acceptance, a larger-working-set result or native parity. Pipe avoids SQL TCP but normal listener startup remains.

## Recommendation and next boundary

Keep the current profile on this evidence. The experiment answers only whether this six-option group under fixed small capacities removes the observed tail: it does not. #88 capacity comparison remains separate. A targeted startup buffer-pool-load OFF contrast was already proposed in #68 and is not changed by this profile; it could test one specific background task mechanism if selected separately. No follow-up is automatically started.

## Reproduction

receipts.zip contains all unique process and memory observations, preflight failure/correction, logs, inventory/source excerpts, plan, input hashes and original collector/build/reducer scripts. Extract into an empty directory and run `python3 analyze.py --check` to reproduce summaries/CSV read-only and reject a missing primary cell, with no temp/build tree needed. Source files and overlay generator are in the measured Git commit; replay archived build.py/run.py in the recorded disposable layout to obtain new measurements. SHA256SUMS.json covers published artifacts. Log path normalization retains original/published hashes. Whole upstream source/cache/binaries are recreatable and discarded after preservation.

No product default/API/guest patch adoption, main integration, CI submission, Qualification or release is authorized or performed.
