# Human Review — page-cleaner startup-tail source correction

**Recommendation:** adopt this narrowly scoped guest-source correction after
Human Review. The approximately one-second Fresh startup mode disappeared in
the bounded four-parallel comparisons on both macOS arm64 and Ubuntu 24.04
x86_64; Ubuntu SQL, Snapshot/Fork and normal Close regression passed. The
strongest objection is that these samples do not establish a universal latency
bound or cover every InnoDB flush/shutdown state. I recommend adoption because
the exact early-signal ordering was observed in the current guest, the source
change closes that ordering, canonical guest and Go regeneration matched
independently, and both tested platforms passed normal runtime integration.
Exact-final-candidate Release CI and broader product validation remain separate;
this review does not merge, tag or publish anything.

The [ordered trace and first hypothesis](https://github.com/masahitojp/mariamem/blob/experiment/startup-tail-wakeup-v050/benchmarks/v050-startup-tail-wakeup-spike.md)
observed a checkpoint target set and an empty-list condition signal between
the page cleaner's pre-lock target read and its subsequent timed wait. The
[source-level spike](https://github.com/masahitojp/mariamem/blob/experiment/startup-tail-source-fix-v050/benchmarks/v050-startup-tail-source-fix-spike.md)
documents the pinned MariaDB file, source hunk, two unqualified development
builds, independent native generation, binary hashes and all paired Go/Python
records. A separate [setting comparison](https://github.com/masahitojp/mariamem/blob/experiment/startup-tail-innodb-config/benchmarks/v050-startup-tail-config-spike.md)
found that disabling InnoDB flush sync did not mitigate the released tail.

## Adopted change and identities

- Baseline: v0.5.0 annotated tag object
  `bfd854da1cecbe71ad761d1578b3f2c710a1c07f`, source commit
  `44100ec676c8c9064f32f3a01bd9a990d487bb61`, guest SHA-256
  `7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`.
  The tag and source commit were distinguished with `scripts/git_identity.py`.
- The only guest behavior edit is in [`guest/source.patch`](../../guest/source.patch):
  after acquiring `flush_list_mutex`, the page cleaner rechecks
  `buf_flush_sync_lsn` and waits only if it is still zero. The preexisting
  idle/timed choice is unchanged when zero. The target writer and signal use
  the same mutex. `guest/experimental.patch` is absent. No converter patch,
  runtime helper, public API or InnoDB default option changed.
- Canonical guest build input commit
  `00702fc87141f48b681e6f01459a0ab4deb7877c`. Two clean Linux arm64
  source builds yielded matching guest SHA-256
  `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`
  (18,368,013 bytes) and linked SHA-256
  `d3022ab3b5f41ffba26b5c4172616ceb4f087c02ffe18569a701ae48fa0bbd53`.
  The source patch SHA-256 is
  `01210ae4f4c10c896b41283137499ac549f606fb6e0d2fad769cf55f1c2d2d16`.
  See [build record](v050-startup-tail-source-fix-evidence/guest.json),
  [phase record](v050-startup-tail-source-fix-evidence/tail-guest-phases.jsonl)
  and [canonical input manifest](../../release/generated-go-build.json).
- The existing goccy wasm2go commit and converter patch set are unchanged.
  After updating only the guest-dependent inventories, the canonical generator
  reproduced every byte of all 94 checked-in generated files on an independent
  second run: [regeneration record](v050-startup-tail-source-fix-evidence/regeneration.json)
  and [phase record](v050-startup-tail-source-fix-evidence/tail-independent-phases.jsonl).
  The published phase record substitutes `<user-home>/` for a local home path;
  the original raw record SHA-256 is
  `33d5aeea4bb2fe3531d9665dfcb6a62d9eb2c6d9cfd7c60eb5400e8ac83ecfec`.
  `scripts/verify_generated_runtime.py` also passed. No Generated Go was
  edited manually. The benchmarked development product and the canonical
  output have identical hashes for 93/94 files; the only difference is the
  development-only `provenance.json`. This bridges the measured executable
  code to this candidate without claiming identical host binary bytes.
- Fixed Binaryen 133 `-O2 --symbolmap` reproduced the new guest hash exactly
  and produced the same 21,693-line function map SHA-256
  `9072658996738894b86effc9b60911db92b413d35cb3c7863f3851666bb645b6`.
  Retained MariaDB/WASIX/library functions were re-audited against a clean
  Git-stamped host and bound in [license evidence](../../release/generated-license-evidence.json).
  Distribution inventory and Python mirror were updated together.

## Verification and limits

| Check | Result | Evidence / limit |
| --- | --- | --- |
| Source patch and two independent Linux arm64 guest builds | PASS | Equal guest and linked hashes; no experimental overlay |
| Two canonical Wasm→Go generations and all 94 checked-in files | PASS | [Regeneration record](v050-startup-tail-source-fix-evidence/regeneration.json) |
| Generated source, license, mirror and public-source checks | PASS | [Full check log](v050-startup-tail-source-fix-evidence/tail-verify-check-retry.txt); 588 Python passed, 37 skipped; Go tests/vet passed |
| macOS arm64 real-guest integration | PASS | [Integration log](v050-startup-tail-source-fix-evidence/tail-verify-integration.txt); race-scoped packages, SQL, concurrent connections, Snapshot/Fork, memory boundary, normal Close, Python 28 passed, snapshot 49 checks |
| Balanced Go/Python four-parallel Fresh comparison | PASS for this fixture | [Spike records](https://github.com/masahitojp/mariamem/blob/experiment/startup-tail-source-fix-v050/benchmarks/v050-startup-tail-source-fix-spike.md): 30 alternating pairs per language, candidate 0/30 tail suites; no failed SQL/transaction oracle |
| Ubuntu 24.04 x86_64 real-guest integration | PASS | [CI run](https://github.com/masahitojp/mariamem/actions/runs/38487541174), [integration log](v050-startup-tail-source-fix-evidence/ubuntu/integration.txt): Go race-scoped packages, SQL and concurrent connections, Snapshot/Fork, normal Close, Python 28 passed, snapshot 49 checks |
| Ubuntu balanced four-parallel Fresh comparison | PASS for this fixture | [Raw runs](v050-startup-tail-source-fix-evidence/ubuntu/fresh.jsonl), [summary](v050-startup-tail-source-fix-evidence/ubuntu/summary.json): baseline 28/30 tail suites and 61/120 tail Starts; candidate 0/30 and 0/120; SQL/commit/rollback oracle passed in every run |
| Final release qualification and public consumers | NOT RUN | Separate release decision and CI responsibility |

### Ubuntu x86_64 adoption check

The [verification-only CI run](https://github.com/masahitojp/mariamem/actions/runs/38487541174)
used Ubuntu 24.04 x86_64, Go 1.26.8 and Python 3.14.8. It checked out probe
commit `5f5cdd43889130ec6d51a991486ab17fb8c03e4e`; its only differences
from reviewed candidate `8d1628f533b573de3124660613b69703040043d9`
were the [CI workflow and comparison script](v050-startup-tail-source-fix-evidence/ubuntu/source-diff.txt).
The runtime guest and generated Go were unchanged. The baseline was the exact
v0.5.0 source commit `44100ec676c8c9064f32f3a01bd9a990d487bb61`.
[Inputs](v050-startup-tail-source-fix-evidence/ubuntu/inputs.json) retain the
independently compiled benchmark binary hashes. The fixture matched the macOS
probe: 10 MiB, eight tables, four parallel Fresh databases, application
connections and commit/rollback. Thirty blocks alternated the arm order;
no completed trial was retried or discarded. The pre-existing tail threshold
was `ready >= 900 ms`.

| Ubuntu Go Fresh startup | v0.5.0 | Source candidate |
| --- | ---: | ---: |
| Starts at or above 900 ms | 61/120 | 0/120 |
| Suites with at least one such Start | 28/30 | 0/30 |
| Start median | 1,091 ms | 144 ms |
| Start p95, nearest rank | 1,139 ms | 179 ms |
| Four-instance suite product median | 2.619 s | 2.049 s |

The matched-block candidate-minus-baseline suite median was -0.568 s. The
individual startup samples and suite timings are in the [raw record](v050-startup-tail-source-fix-evidence/ubuntu/fresh.jsonl);
the [measurement log](v050-startup-tail-source-fix-evidence/ubuntu/measurement.txt)
shows all 60 successful arm runs. The candidate's Ubuntu
`scripts/verify.py integration` passed before measurement: Go integration and
default lifecycle suites, generated-memory checks, Python multi-client/wire/
Snapshot/normal-Close tests (28 passed), and 49 Snapshot checks. This establishes
no regression in the requested normal paths under this test scope. Race-scoped
PASS does not claim general generated-guest race freedom, and 0/120 candidate
tails does not promise a universal upper bound. The Ubuntu result strengthens
the adoption recommendation; it does not replace final release qualification.

The first `verify.py check` run failed one manifest-order test because the
converter patch map had been serialized alphabetically during adoption. The
original fixed order was restored; the focused test and full check then passed.
No converter or patch bytes changed. The corrected check log is retained.

The recorded two-build guest and regeneration proof uses clean input commit
`00702fc`; a final candidate commit necessarily adds generated outputs and
evidence. Local `generated_release.verify_build` passed for that build record,
but it is **not** exact-final-SHA Release CI evidence. When a future release
candidate is submitted, CI must rebuild the exact candidate and run the normal
source/license/platform/consumer guards. The race-scoped PASS does not prove
general shared-memory correctness. The tested default startup mode improved;
`innodb_flush_sync=0`, sustained checkpoint pressure, alternate shutdown
interleavings and other possible tail mechanisms were not separately exhausted.
If those paths show a failed oracle or new wait mode, re-open the source state
machine rather than weakening a guard or promising a universal tail bound.
