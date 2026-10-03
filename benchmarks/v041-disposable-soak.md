# v0.4.1 disposable lifecycle soak

## Decision

**DISPOSABLE LIFECYCLE DEGRADES** for the attempted 16-DB × 50-generation workload
on the reference machine. Two fresh processes crossed the predeclared accounting
budget in generation 3 and generation 2, respectively, with worsening actual
ready latency and CPU. The intended 50-generation plateau was **not established**.
This is a practical budget failure, **not proof of asymptotic growth or a live
Go-object leak**. No production fix or memory policy was introduced.

## Source / environment / method

- Exact released `v0.4.0` source: `39537e9bb2fbbc28315e1ff672960ad734a9e399`.
- Measured harness commit: `b9e8cf393bd24fe8752d1f8e67dd3651007671c5`;
  changes from the tag are diagnostic files only. Runtime is ordinary public
  `Start(ctx, Options{})`, direct-linked generated-Go, without NativeDir,
  guest subprocess provisioning or Wasmer.
- Generated provenance SHA-256: `ade34eabe1dfacba7182ff351a39f3f2f7f06bdd6e89556cf899a7cbc8ade867`.
- Guest SHA-256: `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`.
- Apple M1 MacBook Air, 16 GiB RAM, macOS27.0.1 arm64, Go1.26.8.
- One fresh consumer process per attempt, 16 concurrent fresh DBs per generation.
  Ready ends after each DB's first `SELECT 1`. Every DB then creates a private
  InnoDB table, inserts/updates, rolls back a write, checks the retained value,
  deletes, closes its SQL connection/pool, and normally Closes the server.
  All handles are dropped before the next generation.
- Generation CPU covers self-process before Start through the after-Close
  observation, including the diagnostic parent's observer overhead. Short-lived
  OS-counter helper CPU is excluded. Ready/Close are wall-clock boundaries;
  CPU is not directly comparable to the canonical startup-only CPU boundary.
- Recorded checkpoints are before, all-ready and after Close: HeapAlloc,
  HeapInuse/Idle/Released, TotalAlloc, Sys, NumGC, goroutines, FDs, RSS and macOS
  `phys_footprint`. They are not a continuous transient-peak sampler.
- All builds and measurements held the shared exclusive measurement lock.
  No competing heavy lane ran. No slow generation was removed. Neither GC nor
  FreeOSMemory was forced; normal Go automatic GC remained active.

The [reusable harness and predeclared stop criteria](disposable_soak/README.md)
limit Start/SQL contexts to 30 seconds, the diagnostic process to 15 minutes,
ready/after-Close physical footprint to 12 GiB, sustained FD/goroutine excess
and three consecutive ≥10-second generations. Before the first attempt, an
absolute HeapAlloc guard was removed: `NewWithWASIReserve` allocates a minimum
2-GiB-length guest slice, so 16 guests can logically allocate over 32 GiB while
committing far fewer resident pages. The guard uses the OS footprint boundary,
not a false interpretation of logical Go allocation as resident memory.

The 12-GiB footprint limit is a conservative **accounting budget**, not proof
that this process has 12 GiB of resident RAM. Its limitations matter below.

## Complete measured generations

Memory columns are **after normal Close**, in MiB. Every row had zero SQL,
rollback or Close failures. Ready and CPU include all actual slow runs.

| Fresh attempt | Generation | Ready s | Close ms | CPU sec | RSS MiB | physical footprint MiB | HeapAlloc MiB | FDs | goroutines |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| first valid attempt | 1 | 1.261 | 10.8 | 1.237 | 1831.7 | 3331.1 | 35178.7 | 7 | 1 |
| first valid attempt | 2 | 1.336 | 9.9 | 1.924 | 2139.5 | 10446.0 | 35179.5 | 7 | 1 |
| first valid attempt | 3 | 5.935 | 6.7 | 6.509 | 2702.0 | 41419.9 | 35179.8 | 7 | 1 |
| independent repeat | 1 | 2.059 | 12.7 | 1.780 | 1866.2 | 7275.5 | 35178.9 | 7 | 1 |
| independent repeat | 2 | 5.098 | 7.0 | 5.348 | 2290.1 | 33569.9 | 35179.9 | 7 | 1 |

The first valid attempt completed **48 DBs**; the repeat completed **32 DBs**.
All **80 DBs** completed the full normal workload and shutdown. Both diagnostics
then stopped deliberately on the footprint budget; no timeout/watchdog fired.
The independent repeat stopped within the agreed three-generation diagnostic
budget. There are too few generations to claim a ten-generation window plateau
or a meaningful 50-generation p50/p95. The raw evidence preserves each DB's
ready latency as well as every generation checkpoint.

Within the first attempt, ready time rose 4.71× and CPU 5.26× from generation 1
to 3; in the repeat, ready rose 2.48× and CPU 3.00× from generation 1 to 2.
These actual execution costs provide a practical concern independently of the
interpretation of the unusually high footprint counter.

## Go allocator / OS distinction

After-Close Go counters, all sizes in MiB:

| Attempt / generation | HeapInuse | HeapIdle | HeapReleased | Sys | automatic NumGC |
| --- | ---: | ---: | ---: | ---: | ---: |
| first / 1 | 35180.8 | 9.0 | 7.0 | 35235.7 | 4 |
| first / 2 | 35181.6 | 31676.0 | 12.8 | 66937.7 | 5 |
| first / 3 | 35181.9 | 31675.6 | 13.8 | 66937.7 | 6 |
| repeat / 1 | 35181.1 | 12.9 | 10.8 | 35239.4 | 4 |
| repeat / 2 | 35182.0 | 8203.7 | 9.9 | 43441.0 | 6 |

The source's ≥2-GiB guest slice reservation is confirmed; it explains why logical
HeapAlloc is ~34.4 GiB for this batch. Total allocation history was ~103.1 GiB in
three generations and ~68.7 GiB in two. These are logical Go allocation volumes,
not equivalent physical writes or resident RAM. Automatic GC ran in both trials;
HeapAlloc remained approximately constant while idle heap grew and relatively
little had been released at the observed checkpoints.

The largest reported footprint, **40.45 GiB**, exceeds the machine's 16-GiB RAM,
while RSS was only **2.64 GiB**. It must not be presented as resident-memory use.
The existing [memory-lifetime finding](v04-snapshot-memory-lifetime.md),
**OS PHYSICAL ACCOUNTING DOMINATES**, remains intact: macOS dirty/compressed/
anonymous accounting is distinct from reachable Go objects. This lane does not
identify the exact decomposition of that charge, prove it harmless/immediately
reclaimable, or reinterpret it as a live-object leak.

FDs initially counted 6, became 7 during observer initialization **before the
first DB Start**, and stayed 7 after every Close in both measured attempts.
Goroutines returned to 1 after every Close. The normal FD/worker lifecycle shows
no accumulation in these five generations. This does not validate forced query
cancellation or the known full-guest shared-memory race limitation.

## Diagnostic correction / evidence

The initial tooling attempt stopped before starting any DB because macOS
`os.ReadDir("/dev/fd")` tried to stat a transient pseudo-entry and returned EBADF.
Only the diagnostic was corrected to read descriptor names without per-entry
stat. The failed evidence is retained and is not counted as a mariamem failure:

- [initial observer failure](v041-disposable-soak-observer-failure.json)
- [first valid attempt: full checkpoints / metadata](v041-disposable-soak.json)
- [independent repeat: full checkpoints / metadata](v041-disposable-soak-repeat.json)

External raw work directories are `fanout-v041/evidence/soak-run-01`,
`soak-run-02` and `soak-run-03` under the disposable work root. Raw JSONL SHA-256:

| Evidence | SHA-256 |
| --- | --- |
| observer failure | `a0fee8535bea60d5bc2a00347fa3f569141a5182a28812e9676daf4c60ece8d3` |
| first valid attempt | `45da528e1fbb6bb5bc8e7ed9b5a7bfd741b9cb85cf0297141ba4b929680ccd70` |
| repeat | `cc534a83b1eb57075cd289e385cad5d3c768de9520d810fcbde829e0c66718b3` |

The JSON metadata also records binary, helper and harness checksums. Harness
build, SQL/rollback/shutdown assertions, Python syntax checks and
`git diff --check` passed. No production acceptance or canonical benchmark was
replaced by this diagnostic.

## Product decision input

This evidence does **not** establish that 16-DB disposable generations are
already bounded/practical on the reference machine. The supported normal
shutdown path is functionally clean and rapid, but repeated creation crosses
the conservative accounting budget with a reproducible early latency/CPU cost.
No 50-generation success is claimed.

The next bounded question is allocator/guest-reservation reuse and OS pressure
attribution for this exact released workload, before choosing any fix. It is
not permission for CoW, mmap, forced production GC or storage redesign. A human
must decide the target resource budget and whether this practical failure
warrants a v0.4.x resource project. No implementation is selected or integrated.

**DISPOSABLE LIFECYCLE DEGRADES**
