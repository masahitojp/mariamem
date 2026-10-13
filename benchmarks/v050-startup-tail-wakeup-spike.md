# v0.5.0 page-cleaner wakeup spike — macOS arm64

**Bounded experiment complete; no product fix adopted.** The current 12.3.3
guest reproduced the exact early-signal ordering proposed by the older 13.1
investigation. In three slow Starts, the cleaner read a zero flush target,
the main thread set a target and signaled an empty condition list, then the
cleaner acquired the mutex, saw the positive target, registered to wait, and
timed out roughly one second later. A disposable translated-code candidate
that rechecks the target after acquiring the mutex sharply reduced this tail
in paired Go/Python product workloads. This confirms a tractable cause for
the observed mode, but the candidate is **not** a canonical guest rebuild or
a general latency guarantee. The [Human Review](../docs/reviews/v050-startup-tail-wakeup-human-review.md)
owns the next integration decision.

The [preceding v0.5.0 investigation](v050-startup-tail.md) established the
`mysql_server_init` interval and four-parallel incidence with unmodified
release binaries. This spike addresses its remaining notification-order
question and does not remeasure a 12.3.3-versus-13.1 rate difference.

## Fixed identity and observation

- v0.5.0 annotated tag object `bfd854da1cecbe71ad761d1578b3f2c710a1c07f`
  peels to source commit `44100ec676c8c9064f32f3a01bd9a990d487bb61`
  (`scripts/git_identity.py inspect v0.5.0`). Guest SHA-256 is
  `7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`.
  This branch starts at preceding experiment commit
  `40c8e773592ebe914c466a7dce8fe3e57dbeb0e5`.
- The source interpretation uses [MariaDB's exact pinned commit](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0flu.cc),
  raw file SHA-256 `593c16448b8775055e5aa3d48b36a21dd5152bbfbac675c0f9713b0c0183a620`.
  The canonical guest patches do not change this file. The release
  [function map](../docs/reviews/v050-ad-integration-evidence/function-map.txt)
  identifies `Fn18005=buf_flush_wait`, `Fn18010=buf_flush_page_cleaner`,
  `Fn93=__pthread_mutex_lock`, `Fn218=__pthread_cond_timedwait`, and
  `Fn219=__private_cond_signal` for this Wasm identity.
- Instrumentation is confined to this experiment branch's translated Go and
  [trace source](spikes/startup-tail-v050/). It logs the 12.3.3 target read,
  post-lock target, condition-list head under its lock, waiter-list insertion,
  timed-wait entry/return, and main target set. Event sequence numbers are
  assigned under one tracing lock. The condition signal/list insertion are
  also ordered by the condition's own lock; raw nanoseconds are within a
  process, never compared across processes. The narrowed diagnostic binary
  SHA-256 is `c021e8336a50cd90004b6d7d37c3ce703f68b8d6bbd67644a8ec4c9b337fd656`.
- The first broad futex trace overflowed (50,000 recorded, 102,851 dropped)
  and was excluded from order classification. The subsequent narrowed trace
  reached three slow Starts after four four-parallel suites, below the agreed
  60-suite cap. All 16 instance traces were complete with zero dropped
  events; the three `ready>=900 ms` Starts matched three ordered timeout
  traces. Instrumented incidence is not combined with the preceding
  uninstrumented frequency study. See [observations](v050-startup-tail-wakeup-evidence/observations.jsonl),
  [ordered reduction](v050-startup-tail-wakeup-evidence/ordering-summary.json),
  [raw traces](v050-startup-tail-wakeup-evidence/) and the
  [excluded pilot record](v050-startup-tail-wakeup-evidence/excluded-pilot.json).

| Trial / instance | cleaner target=0 read | target=12288 set / empty-list signal | mutex acquired, live target=12288 | waiter registered | timed wait return | result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 / 30899092152384 | 88.779 ms | 94.888 / 94.889 | 94.891 | 94.892 | 1090.708 | timeout `-73`, wait 995.816 ms |
| 3 / 109484638306432 | 54.299 | 56.089 / 56.089 | 56.093 | 56.094 | 1056.316 | timeout `-73`, wait 1000.222 ms |
| 3 / 109484643172608 | 58.939 | 59.375 / 59.375 | 59.376 | 59.376 | 1060.431 | timeout `-73`, wait 1001.055 ms |

The condition head was zero when the main thread signaled; the waiter was
inserted afterward. A signal to an empty condition is not retained for a
future waiter. The worker had already read target zero before trying the
flush-list mutex and did not recheck it before choosing the timed wait. The
main thread consequently waited for cleaner progress. The 12.3.3 event order
matches the prior [13.1 historical trace](wasm2go-feasibility.md#direct-trace-と原因)
in mechanism; it does not prove equal version-specific frequency.

## Candidate and bounded comparison

The experiment-only [guest/experimental.patch](../guest/experimental.patch)
adds a post-lock `buf_flush_sync_lsn.load()==0` guard around the condition
waits in the pinned MariaDB source. It applies with `patch --batch --forward
--fuzz=0 -p1` to the pinned file. No `guest/source.patch` or release artifact
changed. To test the hypothesis on this Mac without a Linux guest rebuild,
[make_candidate.py](spikes/startup-tail-v050/make_candidate.py) applies the
corresponding skip-wait path to a disposable copy of released Generated Go.
This is a path-level prototype, not proof that the source patch would compile
to identical code on the canonical build. Candidate `p2_pure.go` SHA-256 is
`5d1a294aee01b2545ccec9ba1758688932254bb616c55c78d291332253c5e3ca`;
the source patch SHA-256 is
`d59f6ad6c8b0406038a1fdcc36efd07fb624e898dadacd45bbef5cc7515c0cd5`.

The released Go/Python binaries rebuilt from the exact tag match the prior
[Product Verification identities](v050-product-evidence/verification/build-pair.json):
Go `528e8aa0e28b563d960e3a472d6e117617972ea58178dcee1411e28ba6aca244`,
host `b2b8a9e88e238ede252d8290897b269ce7c09823e6fd9622fdb9a0dcde48dc66`.
Disposable candidate Go/host SHA-256s are
`c81ac4da0fb6d83800741f62b4d13885332fb6feb65f4fa97518939e039229e5` /
`8e7038567300ed936b9240215a8631a38009081b35731a078e39595782751fea`.
All used Go1.26.8 on macOS arm64; Python used 3.14.8. The measured
`10 MiB / 8 table / 4 Fresh DB / 4 worker` workload and SQL/commit/rollback
oracles were unchanged. Python also required successful connect and
`SELECT 1, VERSION()` returning 12.3.3. Each arm ran in its own process,
with baseline/candidate order alternating in 30 blocks. No failed trial was
retried or discarded. The scripts and [paired records](v050-startup-tail-wakeup-evidence/)
retain exact inputs. Suite, rather than four correlated Starts, is the
frequency unit.

| Four-parallel arm | Tail suites (`max ready>=900 ms`) | Tail Starts | Suite wall median | Paired candidate-minus-baseline wall median |
| --- | ---: | ---: | ---: | ---: |
| Go released | 18/30 | 25/120 | 1.755 s | — |
| Go candidate | 0/30 | 0/120 | 1.044 s | -0.646 s overall; +0.013 s when baseline was fast |
| Python released | 26/30 | 41/120 | 1.875 s | — |
| Python candidate | 1/30 | 4/120 | 1.211 s | -0.665 s overall; +0.012 s when baseline was fast |

The [reduction](v050-startup-tail-wakeup-evidence/comparison-summary.json)
records Wilson intervals and all paired cases. All 120 Go and 120 Python
candidate Starts completed their existing product-suite oracles. The Python
candidate's only tail was block zero: **all four** ready times were
1.102–1.103 s, while that block's released arm also had all four at
1.123–1.125 s. It was not guest-phase traced, so its cause is unknown;
do not label it the page-cleaner mechanism or claim the candidate removes
every startup tail. A separate first candidate smoke also had four slow
ready times, followed by a successful smoke with ready 0.245 s; neither
smoke is pooled into the 30-block comparison. The paired fast-baseline
median differences of +12–13 ms suggest no large fixed-cost benefit and
do not establish a regression under other workloads. No Ubuntu, long-run,
or product release qualification was performed.

## Judgment and next boundary

The current guest's one-second mode has a directly observed event order, and
the bounded candidate materially reduces it for the tested fixture. The
candidate does not establish safe behavior for every flush/shutdown state:
it bypasses a wait when a target is present, and the prototype was applied
to translated Go rather than regenerated from patched guest source. Formal
integration requires review of the MariaDB state machine, a canonical
12.3.3 guest rebuild from the experimental source patch, Wasm→Go regeneration
and identity checks, focused flush/checkpoint/shutdown and Start/Close tests,
balanced consumer validation on supported platforms, and normal release
gates. The current branch is intentionally not merge-ready. If the canonical
build changes behavior or exposes a correctness issue, stop and reassess
the source patch rather than promote this translated-code prototype.
