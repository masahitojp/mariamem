# EP1 / EG1 partial-owner and compound-cleanup controls

The consolidated [Live CI40961347571](https://github.com/masahitojp/mariamem/actions/runs/40961347571)
passed both supported hosts, native Python references and the required gate at
actual source_commit `694e8911a817309d077bcfc441a5a8ca01dfe81c`.
[Selected logs, installed receipts and assessment](e2e-ci-40961347571/assessment.json)
retain both full artifact ZIP SHA256 matches against GitHub. The Go registered-job
controls now have supported-host evidence, including the deliberately broken
join hook's Busy/no-generation/no-Resume/no-later-admission outcome.
The public admission subprocess's intentional child failures remain in the raw
log; they are expected negative-control outcomes, not suppressed job failures.

## Next finite gap: controlled owner/error boundaries

Code source_commit `b20decac44225c4b4b2dbed8814f1e7530bd4be1` adds tests only:

- Python and Go partial-start tests now make app stop, Live close, baseline close
  and source close all fail together. Every error remains inspectable, all
  shutdown attempts occur in order, and repeated close does not dispose twice.
- Go simulates Live creation returning a cleanup owner plus an error. All DB
  owners are retained and attempted once; no app startup or case is admitted.
- Python simulates the different SDK boundary: Live construction raises after
  its own internal cleanup, then baseline/source close also fail. The original
  creation exception and both outer cleanup errors remain visible. This is not
  proof that an unreturned host handle was reclaimed.
- Python's expired cooperative hook deadline prevents Reset and later admission;
  shutdown gets a distinct, valid cleanup context. Go's canceled case preserves
  cancellation while StopReap gets a valid context with a deadline.

Local Python3.11 and3.14 each PASS15 component tests. Go
`go test -race -p 1 ./mariamemtest -run '^TestHTTP' -count=1` PASS with no reported
data race. Source identity was checked before verification, and the checkout was
clean at that code source. These results exercise controlled entry owners and
actual language/context semantics; runtime opt-in physical tests are skipped in
this focused Go run. They do not inject new physical engine faults or qualify
this later source on both hosted platforms. Product/engine code is unchanged.

The observed local host is macOS27.2 arm64. The first Go run used the machine's
default Go1.27.3; it is supplementary evidence, not the declared Go1.26.10
profile. The fixed-toolchain result is recorded separately below. Report files
were added after the clean-source checks; subsequent fixed-toolchain checks keep
the same tracked test code, with report-only changes pending.

Fixed-toolchain verification also PASS: `GOTOOLCHAIN=go1.26.10 go test -race
-p 1 ./mariamemtest -run '^TestHTTP' -count=1`, package runtime3.534s after
compilation. No data race was reported. This remains local component evidence
on macOS27.2, not a macOS15/Ubuntu qualification receipt.

Reproduction from b20decac:

```sh
python3 scripts/git_identity.py inspect HEAD
PYTHONPATH=python python3.11 -m unittest discover -s tests -p test_e2e_entry.py -v
PYTHONPATH=python python3.14 -m unittest discover -s tests -p test_e2e_entry.py -v
GOTOOLCHAIN=go1.26.10 go test -race -p 1 ./mariamemtest -run '^TestHTTP' -count=1
```

## Remaining acceptance

These results advance the [acceptance map](e2e-entry-acceptance-map.md), not close
EP1/EG1. Existing protocol/internal Live tests cover late creation/interrupt,
replacement failure, cancellation around commit, concurrent Reset/close and
retained creation-cleanup tombstones with their own controlled backends. Their
scope must remain distinct from an actual E2E application/host fault campaign.
In particular, Go physical-session controls must not be described as direct
BrowserEntry physical fault coverage. The remaining entry-boundary mapping,
concurrent shutdown and actual independent two-owner campaign remain open.

First/second-test workflow evidence, warmup plus three observed four-case batches,
retained baselines1/2/3 and resource/guard observations remain unmeasured for
EP1/EG1. Reuse G1's observer machinery where appropriate, but add observation of
transient old/new Reset children rather than counting only logical Live owners.
No full acceptance, main adoption or release is claimed. #18 retains the work.
