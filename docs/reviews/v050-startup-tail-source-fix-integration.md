# Human Review — page-cleaner startup-tail source correction

**Recommendation:** accept this narrowly scoped guest-source correction for
integration review. Users of the tested four-parallel Fresh workload saw the
approximately one-second startup mode in 24/30 Go and 23/30 Python baseline
suites, versus 0/30 each with the corrected 12.3.3 guest. The strongest
objection is that these bounded macOS results do not establish a universal
startup-latency guarantee or cover every InnoDB flush/shutdown state. I still
recommend the correction because the exact early-signal ordering was observed
in the current guest, the source change closes that ordering, canonical guest
and Go regeneration matched independently, and the normal runtime integration
passed. Ubuntu product validation and exact-final-candidate Release CI remain
separate; no merge, tag or publication is implied by this review.

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
| Ubuntu 24.04 x86_64 product runtime | SKIP | Not available on this Mac; exact candidate CI/platform validation still required |
| Final release qualification and public consumers | NOT RUN | Separate release decision and CI responsibility |

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
