# Python, one host per preparation lineage, heap Snapshot

Experiment only. See [Human Review](../../../docs/reviews/python-heap-snapshot.md).
The caller still uses `mariamem.start()`, `db.snapshot()`, `baseline.fork()` and
context managers. An isolated adapter selects a new Go controller; the installed
Python package and public product implementation are not modified.

Each independent start creates a host. Snapshots, children and derived Snapshots
from that start remain in it. Each child is a separate MariaDB runtime with its
own SQL endpoint. Successful Snapshot consumes its source; closing the last live
handle exits/reaps the host. Parent Close leaves admitted children alive. Owner
EOF asks the host to close all resources. A host crash invalidates the entire
lineage; no automatic replay/recovery is implemented.

## What is compared

- `control`: current Python wrapper, separate host per DB, conventional files.
- `file`: experimental Python adapter/controller, Go conventional file Snapshot.
- `heap`: same adapter/controller, retained immutable 16 KiB Go heap blocks.

All use the same fixed MariaDB guest, SQL workload, logical full-content checks
and source-consumption contract. `file` is a composition control, not a single
variable process-launch benchmark: it also moves ownership verification from
Python into Go. The heap path has no Snapshot payload files, descriptor transfer
or Snapshot mappings. Runtime management directories and Wasm memory mappings
remain. The control does create then unlink files; an empty directory scan alone
is not evidence of never having created files.

## Reproduce

Use a clean checkout of this branch in an experiment-workspace (12 GiB budget,
16 GiB minimum free). Set GO_BIN/GOFMT to Go 1.26.8 absolute paths. Run
`scripts/git_identity.py inspect HEAD`. Apply this directory's `instrument.py`;
it verifies main a8137b8b444f86068d3128a291e3a848adfdfd56 preimages and records
output hashes. It reuses the committed D fixtures and heap templates; only this
experiment's main.go resource-report hook is new to the control host.

Create `<workspace>/temp/venv` with Python3.9 and install the exact versions in
`docs/reviews/python-heap-snapshot-evidence/python-packages.txt` (use
`pip install --no-cache-dir -r ...`). Builds use owned Go caches only.
Run `build.py` under `scripts/experiment_disk.py`, timeout1200. It records source
and binary hashes, runs focused base/snapshot unit tests, builds mariamem-host
and broker. Then run `campaign.py pilot`, `verify.py`, `campaign.py plain` and
`campaign.py resources` under the guard with timeout600. Each Python workflow has
its own process and empty TMPDIR. Localhost binding needs sandbox permission.

Plain uses all six permutations of control/file/heap for each size (6 each).
Resource uses three rotating orders (3 each), separately. Small is 100 rows per
table/256-byte payload; medium is 10000/1024. Same PyMySQL driver and batch size500.
The whole interval includes startup, migrations/seed, Snapshot, two sequential
children's CRUD and close, and final baseline close including broker exit/reap.
Resource snapshots, filesystem scans and heap's final extra integrity audit are
outside whole timing. Metrics run only in the resource campaign; control-host
metrics are saved at process exit and therefore their tiny serialization/exit
cost is included in that separate campaign.

Resource evidence reports the maximum of the individual hosts' RSS high-water
marks, and the sum of their Go TotalAlloc. It does not sum RSS peaks or call them
simultaneous process-tree memory. Python's own maximum RSS is separate. File
cache and Go-external mappings are not measured by Go allocation counters.

`verify.py` exercises real SQL isolation, multiple connections, normal SQL error,
parent/derived Close, concurrent SQL and serialized concurrent Fork requests,
transaction rejection, the existing freeze/corruption oracles, owner EOF,
intentional host SIGKILL and unaffected separate starts. It also runs the existing
pytest fixture shape and an independent in-memory guest Export comparison.
SIGKILL leaves empty Go management directories; the test records them before
removing only empty directories within its owned TMPDIR. Do not call that library
cleanup. No full guest race census or forced worker reclamation is claimed.

Run `summarize.py <workspace>/evidence`, `reduce.py`, restore/reapply and compare
all overlay outputs with build-input.json, then restore canonical files again.
Save templates/harness/reports only; commit/push experiment and clean disposable
worktree/caches via experiment_workspace.py. No release or main integration.

## Bounded prototype limits

Control requests are serialized for the lineage. A long control call delays
other lifecycle calls (SQL runs independently); a Python control timeout disposes
the shared host. Full concurrent routing/per-DB cancellation is not implemented.
Supported subset: start options for timeouts/binary, connection_info, closed,
wait_disconnected, snapshot rollback, fork and close/context managers. Persisted
snapshot/import, status and per-DB logging/options parity are not implemented;
this is not a drop-in shipping Python backend. Multiple xdist workers, large or
many-generation baselines, concurrent performance, non-cooperative runtime exit
and native Ubuntu x86_64 remain outside this spike.
