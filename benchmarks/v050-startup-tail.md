# v0.5.0 startup tail: bounded macOS investigation

**Requested scope complete on macOS arm64.** In the released v0.5.0 runtime, the
approximately one-second ready tail is inside the guest's `mysql_server_init`
interval. A separate one-shot stack sample of a slow Start shows its main guest
thread waiting in `buf_flush_wait` while the page-cleaner thread it spawned is
in an approximately one-second timed condition wait. In the same 10 MiB/8-table
Fresh workload, four concurrent Starts made a suite containing this tail much
more common than four serial Starts. The exact missed-notification order inferred
in the historical 13.1.0 investigation was **not** re-established for 12.3.3.
No startup implementation or public API changed; the diagnostic code on this
experiment branch is not a proposed product patch.

The [Human Review](../docs/reviews/v050-startup-tail-human-review.md) owns the
next decision. This report records observed frequency, intervals, and limits;
it does not compare two MariaDB versions or decide that 12.3.3 caused a new
tail. The previous [v0.5.0 Product Verification](v050-product-verification.md)
had only three trials per cell. Its adverse Go four-parallel Fresh median
0.953→1.763 seconds coincided with different placement of ready tails; those
three samples cannot establish a tail-rate change between versions.

## Fixed inputs and measurement boundary

- Annotated release tag object `bfd854da1cecbe71ad761d1578b3f2c710a1c07f`
  peels to source commit `44100ec676c8c9064f32f3a01bd9a990d487bb61`,
  checked with `scripts/git_identity.py inspect v0.5.0`. Compiled guest SHA-256:
  `7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`.
- Go 1.26.8, Python 3.14.8, macOS 27.0.1 arm64, one local Apple M1/16 GiB
  host. The unchanged Go OwnedPrepared binary SHA-256
  `528e8aa0e28b563d960e3a472d6e117617972ea58178dcee1411e28ba6aca244`
  and Python host binary SHA-256
  `b2b8a9e88e238ede252d8290897b269ce7c09823e6fd9622fdb9a0dcde48dc66`
  exactly match the v0.5.0-side binaries in the Product Verification
  [build receipt](v050-product-evidence/verification/build-pair.json).
  Both were built from the exact release source with
  `CGO_ENABLED=1 go build -p 1 -trimpath -buildvcs=false`.
- Go's existing OwnedPrepared workload used four independent Fresh DBs,
  10 MiB deterministic payload, eight InnoDB tables, application connection,
  SQL/commit/rollback oracle and cleanup. Only `-workers 1` versus `-workers 4`
  differed in the serial/parallel pair. Python used the existing
  `python_product_suites.py` equivalent with the same payload, table count,
  four DBs and transaction oracle. The Python ready interval includes the
  first connection and `SELECT 1, VERSION()`; Go's ready interval ends at
  `mariamem.Start` return. Their absolute ready times are not interchangeable.
- Sixty balanced blocks: all six orders of Go serial, Go parallel unchanged,
  and Go parallel diagnostic repeated ten times. Python serial/parallel order
  alternated in sixty blocks. Each cell was a separate process; no failed
  trial was silently retried. Both `>=500 ms` and `>=900 ms` thresholds gave
  identical tail counts in every arm. The 900 ms threshold identifies this
  observed approximately-one-second mode, not a product pass/fail limit.
  Raw [Go groups](v050-startup-tail-evidence/paired-10mib.jsonl),
  [Python groups](v050-startup-tail-evidence/python-paired-10mib.jsonl),
  [Go reduction](v050-startup-tail-evidence/paired-summary.json) and
  [Python reduction](v050-startup-tail-evidence/python-summary.json) retain all
  observations. Wilson intervals below use **suites** as the unit; concurrent
  Starts within one suite are not independent Bernoulli trials.

| 10 MiB Fresh arm | Suites with ready >=900 ms | Starts >=900 ms | 95% Wilson interval for suite frequency | Suite median without / with ready tail |
| --- | ---: | ---: | ---: | ---: |
| Go serial, unchanged | 7/60 | 7/240 | 5.8–22.2% | 3.097 / 4.089 s |
| Go four-parallel, unchanged | 34/60 | 44/240 | 44.1–68.4% | 1.168 / 1.818 s |
| Go four-parallel, diagnostic | 31/60 | 41/240 | 39.3–63.8% | 1.124 / 1.809 s |
| Python serial, unchanged host | 2/60 | 2/240 | 0.9–11.4% | 2.863 / 3.893 s |
| Python four-parallel, unchanged host | 42/60 | 59/240 | 57.5–80.1% | 0.929 / 1.767 s |

Within balanced blocks, Go had a tail in parallel only in 29 blocks and in
serial only in two; Python had parallel only in 41 and serial only in one.
Thus the four-parallel setting is associated with substantially more
tail-containing suites **for this same fixture on this Mac**. A suite needs only
one delayed Start to be counted; Go's parallel suites had one delayed Start in
24 blocks and two in ten. The user-visible effect is material: the observed
parallel suite median was 0.650 s higher with a tail for Go and 0.839 s higher
for Python. These are descriptive conditional medians, not an additive causal
estimate or a latency promise. SQL/setup work overlaps across workers, and some
longer suites had no ready tail at all. Full suite and phase records retain them.

## Where the second is spent

The released guest already writes an optional startup record to its private
MemFS, but the host's existing diagnostic reader looks in the separate transfer
directory. The experiment-only [source delta](../internal/generatedgo/runtime_instance.go)
exposes that private record to the host after the ready frame. The diagnostic
OwnedPrepared binary SHA-256 was
`de75d6bce5734cc9c3544d23810662763d8d6a6af141b4a6327157bb171b412d`;
it uses the same compiled guest SHA. In 60 diagnostic suites, all 240 host and
guest records were present. All 41 Starts with ready >=900 ms had
`server_init_begin` to `server_init_complete` >=900 ms; no fast/slow
classification disagreed within a host/guest trace. For those 41, median host
`linked_execution_begin` to `ready_header_received` was 1.052 s, median guest
server initialization 1.049 s, and median per-trace difference 3.5 ms. For
the 199 fast traces, the corresponding medians were 48.6 and 45.1 ms.
The traced interval wraps MariaDB `mysql_server_init` in the canonical
[guest patch](../guest/source.patch). The delay is before the wire listener and
client handshake, so neither first SQL nor post-ready setup creates this
particular second in the traced Go Starts.

Instrumentation affects scheduling in principle. A preliminary *sequential*
cohort differed substantially between released and diagnostic binaries and
could not distinguish instrumentation from changing host conditions. We
stopped and redesigned the measurement. Its raw
[checkpoint groups](v050-startup-tail-evidence/samples.jsonl) are retained,
but not pooled into the table. In the balanced campaign, the two parallel arms
had 34/60 versus 31/60 tail suites; 30 blocks ran the unchanged binary first
and 30 the diagnostic first. The unchanged arm had 18 versus 16 tail suites by
those orders; the diagnostic arm had 15 versus 16. In the 14 blocks where both
parallel arms were fast, the median diagnostic-minus-unchanged suite difference
was 1.4 ms. This removes the earlier obvious time-order confound and finds no
large diagnostic shift in this campaign; it does **not** prove identical
population tail rates or prove every untraced tail has one cause.

For a narrower location check, a **separate** diagnostic binary sampled Go
stacks once at 250 ms in one slow four-parallel suite. Its SHA-256 was
`0207958cdd8aa1b95d5cc0075a22617f16a4664afa09c27c9e970d0b9ac1c0c3`;
it was never used for frequency counts. In the captured slow Start, the main
guest goroutine was in `AtomicWait32At` beneath `Fn18005`; the corresponding
page-cleaner goroutine, created by that main goroutine, was in a timed
`AtomicWait32At` beneath `Fn18010` with approximately 0.998 s remaining.
The released guest's pinned
[function map](../docs/reviews/v050-ad-integration-evidence/function-map.txt)
maps `Fn18005` to `buf_flush_wait` and `Fn18010` to `buf_flush_page_cleaner`.
The [selected stack](v050-startup-tail-evidence/stack-excerpt.txt),
[full stack](v050-startup-tail-evidence/stack-probe-full.txt), and
[matching guest trace](v050-startup-tail-evidence/stack-probe-trace-3.json)
support that call-path conclusion. A one-shot stack cannot show the order of
signal, registration, and timeout return. The historical
[13.1.0 characterization](wasm2go-feasibility.md#mysql-wire-startup-tail-characterization)
observed such an order in its different guest and is supporting context,
not a substituted 12.3.3 trace.

## Judgment and limits

The requested wait interval, bounded incidence, and association with
four-parallel Fresh are established for this v0.5.0 Mac campaign. The evidence
supports a MariaDB page-cleaner/flush-wait path, but a specific missed-wakeup
event order in the current guest remains unconfirmed. No SQL errors, hangs,
crashes or failed cleanup/oracles occurred in these trials. The old guest also
had an approximately-one-second page-cleaner tail, so this study provides no
basis to call the 12.3.3 upgrade the origin of the phenomenon. It also does not
measure a matched v0.4.7 tail rate, Ubuntu frequency, longer-run rates, or
different fixtures; those remain outside the user-selected v0.5.0 scope.

The source diff only repairs diagnostic access and adds a one-shot stack sample
on this experiment branch. It must not be merged into main as a performance
fix. Any optimization should first establish the current guest's exact
notification sequence, then keep correctness and performance evidence separate.
The [capture scripts and hashes](v050-startup-tail-evidence/) are retained so a
reviewer can reproduce the bounded design without relying on a median of three.
