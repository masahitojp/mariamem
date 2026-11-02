# D1 local xdist adoption — 2026-11-03

The Human approved adoption after installed-wheel acceptance and local timing.
Recommend integrating explicit local workers: both OSes/minors passed the
installed entry, with serial still default. The strongest objection is duplicated
worker preparation and repeated class setup. Explicit counts, documented class
activation semantics and retained serial execution bound that tradeoff;
resource efficiency remains unmeasured.

## Identity and acceptance

Reviewed base: `f09d5167172f091ccc0b20f78b817fe870d3cadf`.
Reviewed candidate source_commit: `d99f07cd16a8a11c1644225206a3d1fcc0a39edd`.
[Release CI41457221670 attempt3](https://github.com/masahitojp/mariamem/actions/runs/41457221670)
succeeded, operation=verify, READY, no publication. The final PR cleanup changes
documentation/evidence only. READY remains bound to that candidate, not relabeled
to a later documentation commit or squash.

Downloaded inputs record installed=true and matching adapter and embedded host
source_commit in every cell. Parent PASS counts expected failure scenarios as
successful detections; original subprocess failures remain visible.

| OS | Python | Entry | Assessments | assessment.json SHA256 |
| --- | --- | --- | --- | --- |
| macos-15 | 3.11 | prepared | 20 PASS | `c58fe66075c3fbdd10bbf2ea39c01240d6f26d1b4032e3bff5b6464a7ee499d8` |
| macos-15 | 3.11 | parallel | 15 PASS | `862184128757b595874a246c5b89fab61286f0bdf06a7bda8d4bc82ae8660b82` |
| macos-15 | 3.14 | prepared | 20 PASS | `c58fe66075c3fbdd10bbf2ea39c01240d6f26d1b4032e3bff5b6464a7ee499d8` |
| macos-15 | 3.14 | parallel | 15 PASS | `46ffda4d1baacfa94a84383e1886f686e7aafdf9c8817913f320f0266dfbae53` |
| ubuntu-24.04 | 3.11 | prepared | 20 PASS | `c58fe66075c3fbdd10bbf2ea39c01240d6f26d1b4032e3bff5b6464a7ee499d8` |
| ubuntu-24.04 | 3.11 | parallel | 15 PASS | `b2690604ab6f18f6289358928f7a49b538a113a45184cc07e2607963f14045d3` |
| ubuntu-24.04 | 3.14 | prepared | 20 PASS | `c58fe66075c3fbdd10bbf2ea39c01240d6f26d1b4032e3bff5b6464a7ee499d8` |
| ubuntu-24.04 | 3.14 | parallel | 15 PASS | `862184128757b595874a246c5b89fab61286f0bdf06a7bda8d4bc82ae8660b82` |

READY receipt SHA256: `fa612681981ff4032274362487fcc22c95947e97a53a19f6aefabdd9c6236550`.
Artifacts: `django-<OS>-d99f07cd16a8a11c1644225206a3d1fcc0a39edd` and
`release-ready-d99f07cd16a8a11c1644225206a3d1fcc0a39edd` in the linked run.

## Conditions and detection

- Both OSes × both Python minors: satisfied above for serial and parallel.
  Existing Release Django job and aggregate reject incomplete cells.
- Staging notes: present in `docs/release-notes/unreleased.md`; completeness is
  editorial and not detected by CI.
- Routing/shadow_maria exclusion: documented in `docs/django-prepared.md`,
  enforced by collection/setup guards and covered by policy/API tests.
- Worker-owned lineage, death/restart, idle/no-DB, restoration and cleanup debt:
  covered by `tests/django_prepared/xdist/run.py`. Cleanup injection is not real
  engine I/O failure. Host EOF exit does not guarantee Python scratch finalizers.
- Current usage docs are synchronized to approved-but-unreleased wording.
  No generated inputs, Go/guest source, baseline pins, version metadata or
  published installation contract changed. No further blocking gap found within
  this finite scope. Arbitrary applications/resource scaling remain unproven.

## Evidence placement and remaining boundary

The product PR retains implementation, deterministic tests, reusable acceptance
harnesses and concise summaries. Detailed local event/JUnit/stdout dumps remain
in the [pinned archive](https://github.com/masahitojp/mariamem/tree/85f2857df5f47586a10ac85a6daf46d3927ca438/docs/reviews/d1-xdist-implementation-evidence), preserved by the pushed experiment branch.
The original [checkpoint](d1-xdist-implementation.md) retains reproduction commands.
[Timing report and recipe](https://github.com/masahitojp/mariamem/blob/85f2857df5f47586a10ac85a6daf46d3927ca438/benchmarks/d1-xdist-timing/README.md)
remain outside the product PR: M1/Python3.11,3 measured repetitions,240 tests
14.00s serial vs5.76s at4 workers. This is not cross-platform or CI-latency proof.
Normal protected integration remains required. Adoption does not select a
release version or approve publication. No heavy rerun is needed for removing
logs and synchronizing prose while executable files remain identical.
