# Issue #5 — TEXT/BLOB duplicate-removal investigation

2026-10-29 JST. Investigation branch `experiment/issue5-text-dedup`, starting
source_commit `cc00ccd98e29a1f5d5088a082be90a3cdaa4f469` (main). No integration,
release, guest-source change or CI submission is included.

**Conclusion:** this is a mariamem host integration defect. The internal Aria
temporary-table scan requests a file mapping; WASIX libc duplicates its file
descriptor, but mariamem's `host.Fd_dup` explicitly panics. The worker disappears
without replying. Its panic is retained until worker joining, so the pending
query reaches its timeout, which terminates the whole database. It is not an
infinite SQL loop, allocator exhaustion, or a blocked host filesystem call.

Recommend a separate bounded production change to bind `Fd_dup` to the existing
descriptor implementation, with canonical regression coverage and both-platform
validation. A diagnostic delegation removes all 19 observed failures and matches
native results in all 28 cases on macOS arm64. The strongest concern is that this
enables a previously unexercised descriptor/mapping path: the small SQL matrix
does not prove descriptor lifetime, resource cleanup, Snapshot/Fork interactions
or Ubuntu correctness. Those remain acceptance conditions, not assumed PASS.
The independent worker-trap notification weakness also needs an explicit scope
decision; fixing this import alone cannot prevent timeouts from other traps.

## Evidence and causal path

- [Exact inputs and binary build identities](issue5-text-dedup-evidence/identity.json).
  `scripts/git_identity.py inspect HEAD` identified a commit before each build.
  Baseline binary has `vcs.modified=false`; diagnostic binaries correctly have
  `vcs.modified=true`, and their patches are retained below. Go1.26.10,
  CGO_ENABLED=0, darwin/arm64; Python3.14.9 and PyMySQL from the existing local
  venv. Native control reports `12.3.3-MariaDB-ubu2404`, Docker image digest
  `sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1`.
  This control uses a different image digest from the original dbt investigation;
  its actual server version was checked. No timing comparison is claimed.
- [Baseline probe](issue5-text-dedup-evidence/probes.json): EXPLAIN says
  `Using temporary`; another already-open session returns `SELECT 1` during the
  failure. Default and tiny tmp-table limits both reach the four-second timeout.
  `big_tables` returns1193 (not available in this embedded profile).
- [SIGQUIT stack](issue5-text-dedup-evidence/stack.txt): main guest dispatch waits
  for another input frame, a surviving session worker waits for work, and the
  failed request waits for a response. The failed worker is absent. SIGQUIT is
  deliberately destructive to this one diagnostic DB, and is distinct from the
  ordinary timeout observations.
- [Diagnostic-only patch](issue5-text-dedup-evidence/diagnostic.patch) prints the
  panic at `base.ThreadLaunch`'s existing recovery boundary. The
  [captured trap stack](issue5-text-dedup-evidence/default-diagnostic.txt) proves
  `unimplemented WASIX: Fd_dup` in `internal/generatedgo/main.go`, through
  generated functions `Fn240 ← Fn5168 ← Fn5201 ← Fn5387 ← Fn13032`.
  The corresponding [diagnostic observation](issue5-text-dedup-evidence/probes-diagnostic.json)
  still reaches the same timeout and still allows a sibling `SELECT 1`.
- `ThreadLaunch` records the panic in `Threads.trap`. `executeGuest` only reads
  it through `WaitThreads` when the root returns. The resident root is still
  reading commands, and the C worker never reaches `multi_reply`, leaving the
  wire layer waiting. This explains the silence before timeout.

Pinned MariaDB source_commit
`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` explains the path. Function names below
are mapped by the inspected source and generated bodies, rather than by a retained
Wasm name section:

1. [`Create_tmp_table::choose_engine`](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_select.cc#L22456)
   selects `TMP_ENGINE_HTON` for blob fields or a unique constraint, rather than
   HEAP. This is a temporary-table engine/path boundary, not evidence of an
   in-memory HEAP hash loop.
2. [`init_read_record`](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/records.cc#L179)
   calls `extra(HA_EXTRA_MMAP)` for an internal temporary table without addon
   fields. This matches the `Fn13032` scan setup in the trap stack.
3. [`maria_extra`](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/maria/ma_extra.c#L473)
   invokes `_ma_dynmap_file`, under its internal mutex, for `HA_EXTRA_MMAP`.
4. [`_ma_dynmap_file`](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/maria/ma_dynrec.c#L55)
   requests read/write `MAP_SHARED | MAP_NORESERVE` over the data file plus a
   small margin. Its generated body `Fn5168` passes length+7, protection3,
   flags16385 and the data FD to `Fn240`, which calls the WASIX `Fd_dup` import.
   The diagnostic stack records this exact call, with length47 and FD52.
5. mariamem's explicit `Fd_dup` override panics, even though the embedded
   `base.WasiStubs.Fd_dup` already implements shared offset and reference-counted
   final close. The override masks that implementation.

**Correction to the original hypothesis:** `SQL_BIG_RESULT` selects
`Using filesort`, with both Created_tmp_tables and Created_tmp_disk_tables still0
after success in this probe. It avoids this temporary-table path; success is not
evidence that a disk temporary table fixes an in-memory-table defect. Prefix
indexing and reducing tmp-table size do not remove the missing import.

## Bounded intervention and regression

The [delegation spike](issue5-text-dedup-evidence/fd-dup-spike.patch) changes only
the Go host override to call `h.WasiStubs.Fd_dup`. Its binary also includes the
diagnostic printing patch. No guest, converter, generated function body,
canonical source patch or release pin changes were made. Both live Go edits
were restored after the experiment; only their reviewable patch artifacts remain.

| Actual macOS observation | Unmodified host | Diagnostic delegation |
| --- | --- | --- |
| Native/guest matrix |19 differences,9 matches|28/28 matching outcome, rows and affected count|
| New canonical wire regression |3 FAIL|3 PASS|

The [before matrix](issue5-text-dedup-evidence/matrix.json) and
[spike matrix](issue5-text-dedup-evidence/matrix-fddup.json) cover the ten types
and eighteen additional shapes from the issue. Native returns OK for every
case. Each guest case owns a new DB and uses a one-second query timeout.
Rows are compared without assuming an unspecified SQL row order.
The fixture is intentionally tiny; no broad text/collation or large-input claim.

The added `tests/test_python_wire.py` regression exercises VARCHAR(1000), TEXT
and BLOB with duplicate values, DISTINCT, UNION, GROUP BY and CTAS, then SQL on
both original and sibling connections. It belongs to the existing opt-in wire
integration boundary. [Before](issue5-text-dedup-evidence/regression-before.txt)
and [spike](issue5-text-dedup-evidence/regression-spike.txt) logs retain the same
test names. The investigation branch deliberately retains the failing regression
without applying a production fix; it is not merge-ready.

Existing ordinary CI cannot detect this defect at the baseline: the public wire
matrix had no TEXT/BLOB duplicate-removal case, and lower-level descriptor tests
cannot detect an overriding host method that never delegates. The new actual
guest test closes that concrete SQL reachability gap when included in CI. It
does not cover arbitrary worker traps or their timely notification.

## Remaining work and cost

Root cause investigation is complete on one platform. Production implementation
and adoption are separate work. The narrow host delegation is a few lines, but
the acceptance cost is more than that diff:

- Add direct tests of the actual host import (valid/invalid FD and output
  pointer, shared offset, closing either alias first, final close), and inspect
  file-mapping duplicate cleanup and per-FD flags. Existing base `Fd_dup2`
  controls are not proof of this host `Fd_dup` binding.
- Run canonical check and focused wire regression on macOS and Ubuntu; inspect
  post-query connection/resource cleanup and Snapshot/Fork after mapped temp
  table use. Run the same native matrix on Ubuntu before proposing adoption.
  Budget one implementation/test pass and one both-host Development CI run;
  build/cache cost is environment-dependent, not measured by this investigation.
- Decide whether to include timely worker-trap notification in that repair or
  track it separately. It needs an injected trap test proving prompt failure and
  safe cleanup, without continuing to serve a partly failed DB. Do not convert
  unsupported imports to silent success or broadly recover and continue.
- No guest source change is required by the demonstrated cause. If later
  mapping semantics require a guest change, obtain separate Human approval;
  this investigation grants none.

No Ubuntu run, full canonical suite, release acceptance, new CI run, dbt replay
or production readiness is claimed. No GitHub comment was posted. A concise
issue-update draft is retained beside the evidence for a later authorized update.

## Reproduction and retention

Build a clean checkout at the source_commit above using
`GOTOOLCHAIN=go1.26.10 CGO_ENABLED=0 go build -trimpath -o <host> ./cmd/mariamem-host`.
Use a disposable workspace guarded by `scripts/experiment_disk.py` with
`--min-free-gib 8 --budget-gib 6 --timeout 900` for builds and600 for the matrix.
The probes use an existing Python environment with PyMySQL:

```sh
python probe.py <absolute-host-path>
python matrix.py <absolute-host-path>
```

`matrix.py` expects native MariaDB on localhost33315 with root/empty password and
owns/drops its `issue5` database. Start the pinned image above with
`MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=1` and a localhost-only33315:3306 mapping.
Reproduce the spike with `git apply --unidiff-zero` on both saved patches, building to a name containing
`fddup`, and rerunning the matrix; that name selects a separate output file.
The diagnostic-only probe uses a binary name containing `diagnostic`.
Run the canonical regression with PYTHONPATH=python, MARIAMEM_TEST_DEFAULT=1,
MARIAMEM_TEST_HOST=<host> and
`python -m pytest tests/test_python_wire.py -k text_blob_duplicate --tb=short -q`.
The unmodified binary must fail; the diagnostic delegation must pass.

Retain reports, scripts, patches, JSON, selected small stacks, input hashes and
the regression; delete rebuilt binaries, copied upstream source and owned
scratch after collection. The failed initial workspace preparation attempted a
worktree before Git write permission was granted and created no worktree; its
receipt's old base SHA is not a measurement identity. Actual builds used the
explicit identity record above and the current experiment branch.

Cleanup removed301,105,152 bytes of owned scratch, stopped/removed the native
container and cleared the Go build cache after checking no active compiler,
linker or guest host remained. The helper reports no owned cleanup debt and no
retained experimental path above1GiB. The repository aggregate is about1.05GiB,
retained for tracked product/generated source, Git history and pre-existing
compact evidence; no individual child directory is above1GiB. Unrelated
experiment evidence was preserved. See the [summary](issue5-text-dedup-evidence/summary.json)
and [evidence checksums](issue5-text-dedup-evidence/SHA256SUMS).
