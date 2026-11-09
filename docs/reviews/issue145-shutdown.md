# Issue145 shutdown implementation evidence

The approved implementation selects shutdown by purpose: Snapshot capture/export
uses `innodb_fast_shutdown=1`; discarded fresh/Fork databases use `2`.
The local evidence supports continuing to both-platform CI. Main adoption and
release remain separate decisions. The strongest objection is the cost of an
additional internal session on light databases; this bounded comparison found
almost no benefit without writes and does not establish workload-wide speedup.

## Candidate and mechanism

Runtime source_commit `60717a1ea16f8b16a8255a6192e85a9465f6226d`, based on main
`279fa530d03cab1bd025df91bf5130bbf845a721`. Later documentation/evidence and normal-CI smoke routing changes
do not alter tested runtime/test bodies. Earlier results on old source4cf4393d
and candidate7a407c6b are exploratory only and are not current-main acceptance.

After admission stops and all client cleanup joins, a private guest session uses
freed slot0 to select the mode, closes that session, and stops the engine. A
client's global setting cannot override the purpose; a Fork may become another
clean Snapshot. Configuration/transport failure uses existing abort and retained
disposal behavior instead of successful capture. Current main's join/disposal
ownership remains intact. No canonical guest, generated runtime, public API or
release ledger changes are needed. Rollback during client cleanup remains.

Deterministic tests observe the selected mode at the actual stop/export frame
and reject successful completion when SET fails. Public integration covers a
client setting2, Snapshot, Fork, setting2 again, an active uncommitted update,
rollback/reSnapshot, restored committed value, active-transaction Close,
idempotent Close and an independently usable sibling.

## Local verification

macOS arm64, Go1.27.3. Git object identities were inspected with
`scripts/git_identity.py`; built candidate stamp is clean and bound to60717a1e.

- `scripts/verify.py check`: PASS. Includes source boundary67, all Go packages,
  vet, Python1887 +114 subtests (98 skipped), native8 and public-source check.
- `scripts/verify.py integration`: overall NOT PASS. Race package group, complete
  Go integration/default/memory/worker controls, Go/Python Live smoke, Python53
  (1 skipped), and33 Snapshot checks PASS. The final prepared-consumer step
  stopped because the reused Python3.14 venv lacked mysql.connector.
- The final step was independently retried with fixed connector26.7.0 in a
  disposable Python3.11/OpenSSL3 venv. Its native comparison correctly rejects
  `python_minor` mismatch against the macOS3.14 reference. Local3.14 has OpenSSL4;
  no driver patch, synthesized ssl constant or relaxed profile was used. This
  retry is NOT a passing consumer acceptance. The comparison receipt preserves
  functional FAIL/PENDING, not a new accepted limitation.

Both-platform normal CI, including its supported Python/OpenSSL consumer profile,
remains required. No Linux acceptance or stable tail/resource improvement is
claimed. Published text logs replace personal home paths with `<USER_HOME>/`.
The new public regression also runs in normal CI smoke, in addition to full
integration; its purpose selection must not depend on manual release testing.
Logs and exact matching failure are in
[the evidence directory](issue145-shutdown-evidence/).

## Bounded matched Close measurement

Same macOS, Go1.27.3, current canonical guest, two binaries, six alternating pairs
per cell (48 DBs). No extra caller SET is timed: candidate internally selects2.
Each DB has disconnected/cleaned-up SQL sessions before Close. Write workload is
1000 rows ×1024 bytes; fresh INSERTs, Fork updates every row. Every Fork checks
1000 rows/1024000 payload bytes before optional UPDATE. Both baselines are taken
with normal clean Snapshot semantics. Successful cleanup completes in every cell.

| Close median ms | Main runtime baseline | Candidate |
| --- | ---: | ---: |
| fresh, no writes | 7.562 | 7.461 |
| fresh, written | 7.257 | 3.931 |
| Fork, no writes | 1.929 | 2.004 |
| Fork, written | 7.581 | 2.165 |

Fresh includes final Python host-process disposal; Fork retains a Snapshot owner.
Compare each row's two binaries, not fresh versus Fork absolute times. Six pairs,
one host and ~1MiB do not establish production distribution/tail behavior.

The baseline was built using Go `-overlay` to substitute exactly the two changed
production Go files from main279fa530 into candidate60717a1e's checkout. All other
production/guest inputs match main. Both VCS stamps identify the candidate
checkout: **the baseline binary stamp is not its runtime source identity**.
`matched-inputs.json` records baseline runtime identity and per-file SHA256;
`main-*-binary.txt` and `main-binaries.sha256` preserve actual stamps/hashes.
This avoids another large generated-source checkout and does not relabel a
candidate binary as an independently clean baseline checkout.

Reproduce in disposable scratch: inspect both commits with git_identity.py;
extract `internal/host/server.go` and `internal/host/heap_snapshot.go` from the
recorded baseline commit with `git show`, create the Go overlay Replace map,
build `baseline-host` using that overlay and `candidate-host` without it. Place
both in scratch/temp and run saved `matched_probe.py` from scratch/evidence using
candidate `PYTHONPATH=python`, PyMySQL, and the source SDK. Binary paths are derived
from the script directory. Save raw samples, summary, stamps, hashes and toolchain.

Generated binaries/venv/worktree are disposable after preserving the branch and
compact evidence. The user's original dirty worktree is outside this candidate.
