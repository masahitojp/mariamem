# Issue154: bounded experimental execution stage

The Human requested proceeding after CI43105781665. Reuse its exact single
UNQUALIFIED guest at f43257225e1fd65c58ea8f5d7b220c3a509c203b; do not rebuild C,
change canonical adapters, relabel the origin, integrate or release.

Question: does the prepared private-copy guest preserve full-table contents,
SQL/collation semantics and child/cleanup behavior? Budget: active2h, tooling30m,
one heavy CI submission; one Ubuntu24.04 x86_64 job with a60-minute ceiling.
No local generated-host build or new timing campaign. Mac acceptance and
observer-off Pipe P4/P8 comparisons remain later stages. A failure remains a
failure with its phase/source, not a request to relax a guard or loop retries.

## Binding evidence and limit

[The additional comparison](execution-binding.json) resolves the +34 pointer to
an identical NUL-terminated InnoDB future-LSN diagnostic string. CRC's four
lookup slices remain the same4096-byte table at+749632. Its initialized4-byte
global is zero at both addresses. Fn153/Fn214 change only integer literals, all
+749632; Fn131 is unchanged. Mutable BSS references move by the same amount,
with unchanged access widths/offsets and control/call tokens. We have not proven
all BSS symbol names from debug info. This is sufficient to try the **exact**
experimental bindings with differential/worker/cleanup controls, not to declare
ABI parity or authorize product adoption.

CRC's prior compact comparison included one trailing newline; the canonical
installer's whole-function extractor excludes it. The actual extractor yields
`2569b9f4e7022921787050ec11e7fae5b14382416adc732fae562c8f6aca236e`.
Local application of the unchanged complete-body/table validators and CRC block
edge checks to the downloaded candidate succeeds. Old receipts are not changed.

`tests/uca_copy_bindings.py` loads checksum-pinned copies of the original adapters
into the experimental installer process, substituting only the fixed new guest,
whole-function hashes and table offset. No API accepts arbitrary hashes/offsets;
no fuzzy/relocation-normalized body is admitted. Original files and canonical
acceptance stay unchanged. Unit controls reject wrong guest, missing inputs,
modified adapter source/function/table. Every original transform still executes.

## Runtime input identity

The workflow checks out two clean trees: exact execution HEAD and immutable guest
origin f4325722. It downloads the two original ZIPs and verifies full SHA256 before
use. The existing development guest/toolchain/source verifier runs against its
original tree. The converter/source adapter is reproduced once (no C build), and
the entire candidate inventory must match the prior authenticated assessment.
This retains the existing verifier's required converter executable/provenance
instead of bypassing checks for files absent from the CI source-only archive.

The existing installer is called in-process with experimental adapter copies.
Its source/data/translation/static-image checks are unchanged. An isolated host
copy carries the generated result, selected guest compatibility identity and one
new actual-guest test. Its SDK/host runtime comes from the original tree; the
execution harness/acceptance tests come from the current HEAD. Both identities
and the built host hash are recorded separately. Neither checkout is rewritten.

## Finite acceptance in this submission

- Native MariaDB12.3.3 at the existing pinned image: UCA values/order/grouping,
  comparisons/weights, uniqueness errors, contractions, five encodings,
  default/variant operation orders and generic alias.
- Actual guest: all15 default profile/level copies compared to the original
  producer by the private verification switch; ambient/timing separation;
  exact prepared flag table mutation rejected with the verifier enabled, while
  the same mutation without the verifier must not cause a startup failure.
  Existing prepared UCA/lexer and worker-trap checks remain selected.
- Existing CRC checksum/page-validation differential after the exact new binding.
- Native SQL parity, two independent children, original baseline preservation,
  child-to-reSnapshot inheritance, transactions and confirmed session disposal;
  actual-guest tests also compare active mapping counts.

These are pending until CI executes. Operation order is not proof of lazy
internal initialization order. Allocation-failure/retry coverage still comes
from the prior exact-source/stub harness, not real-guest OOM injection. Do not
upgrade that claim because runtime controls pass. Inspect these residual limits
at the correctness exit before any adoption or timing claim.

Local validation:129 focused tests; complete downloaded-body/table transform
checks; Python AST, workflow shell syntax, Go fixture gofmt,
source/ABI difference inspection and diff check. No runtime PASS is claimed.
Full generated sources/logs remain short-lived CI artifacts. Preserve only compact
receipt/hash/analysis in the repository. Submit the run URL and stop monitoring.

## First execution failure — CRC test fixture relocation

[CI43132716457](https://github.com/masahitojp/mariamem/actions/runs/43132716457)
at c83e8c77353649d346ed8153c01873799d855a87, job130900504503, successfully
collected native12.3.3 SQL reference, reproduced the exact candidate inventory,
installed the experimental bindings and built host SHA256
`fe4d0332a57f38457c22fdac42ff8e95b0a420312f1603ffa550860c8f67614d`.
Artifact13906067943 ZIP SHA256
`e548f23948d0518bab0597ff7f319399348595102c454d42530cea5e01d38b3f`
was verified locally. CRC calculation passed832 length/alignment cases plus
independent bitwise/known-vector checks. Page validation then failed on the first
payload mutation (size4096, offset0, original=0, fast=0). Actual UCA/worker tests
and guest native-SQL/children/reSnapshot acceptance did **not** execute.

The experimental runner overlooked two absolute addresses in the inherited
`crc32c_test.go` setup: the lookup table was copied to15569536 instead of16319168,
and page size was written to26865072 instead of27614704. These are the same
+749632 relocations already recorded for the validator. The fresh fixture memory
is zero-filled, so the validator read an unset page size and an uninitialized
table while the test wrote to the old positions. Agreement between original and
fast validators alone did not hide this: the independent corruption oracle
correctly failed. This is an experiment fixture omission, not evidence of a
product CRC regression or of UCA correctness.

The fix transforms only the isolated test copy after checking the complete
original fixture SHA256. Its two setup literals change; all remaining bytes,
including every rejection/LSN/memory-mutation assertion, are preserved. Canonical
test/adapter/guest/runtime files remain unchanged. Installation records both
fixture hashes and the explicit replacements. Eleven focused tests pass,
including changed-oracle and already-rebound fixture rejection; syntax and Go
format checks pass. The runtime fix is pending one corrected Ubuntu submission
under the same60-minute ceiling; no C rebuild, broader campaign or release.

## Ubuntu correctness completed — 2026-11-12

[CI43137408120](https://github.com/masahitojp/mariamem/actions/runs/43137408120),
execution source a197034c6dabd663c84262323d6b42c5c20fb2a2, completed the full
bounded Ubuntu job. [Compact receipt](ci-43137408120.json) and its
[checksum](ci-43137408120-SHA256SUMS.json) retain exact job/artifact/source/guest/
host identities and all10 verified artifact-file hashes. No raw logs, REST payloads
or duplicate generated sources are committed.

| Selected check | Ubuntu result |
| --- | --- |
| CRC calculation and page validation | PASS:832 length/alignment cases plus known vector;80 valid/corrupt/LSN cases |
| New private-copy UCA full-byte oracle | PASS:15 profile/level comparisons |
| New table corruption and verification separation | PASS:enabled verifier rejects; normal/ambient/profiling controls pass |
| Existing UCA/lexer/worker protection | PASS:six UCA levels,638 lexer descriptors, corruption and peer survival controls |
| Native MariaDB12.3.3 SQL/collation | PASS:serialized semantic result equals native reference |
| Two children and preserved baseline | PASS:independent mutations and baseline observations |
| Transactions and child reSnapshot | PASS:two real-host pytest cases, no skips |
| Completed disposal | PASS:refs0/process exit0/reaped/root absent; actual-table mapping assertions pass |

The compiled host SHA256 equals the preceding failed run. Thus the CRC test
setup correction resolves that failure without changing the executable. The
installation record still says runtime_acceptance=false because it was written
before the tests; the separate test results above supply bounded acceptance and
do not rewrite that historical phase record.

This completes the Ubuntu prototype correctness checkpoint. It does not complete
Mac platform acceptance, performance evaluation, real-guest OOM injection, all
BSS-name proof or lazy initialization-order proof. Existing source/stub failure
coverage and query-order claims retain their stated limits. No new runtime or
heavy CI was run when collecting this receipt.

Next recommendation: verify this same guest on Mac, then compare baseline and
candidate with verification/timing diagnostics disabled, fixed Pipe P4/P8 inputs,
and alternating order. Report Fork and complete-suite time together; retain
tails. A correctness PASS is not evidence of speedup or product adoption.

## Mac correctness submission — 2026-11-12

The Human authorized continuing after the Ubuntu checkpoint. Reuse exactly the
same f4325722 guest and translation artifacts; reproduce only the converter,
installation and arm64 host build. The separate `uca-copy-mac.yml` job targets
macOS15 arm64 and asserts the architecture. It does not retrigger the Ubuntu
job or the C build. Budget: active2h including tooling30m, one heavy CI submission,
60-minute job limit. Local work is workflow/reference verification only.

Repeat the same CRC, actual-table/corruption/worker, native SQL/two-child,
reSnapshot and confirmed-disposal checks. The native server is **not** rerun on
Mac: `uca_copy_reference.py` authenticates Ubuntu artifact13908017919's complete
ZIP, original source and native-result bytes before reuse. Its provenance travels
with the new result. Missing/expired or mismatched evidence stops the job; it must
not fall back to another run. Old Ubuntu PASS remains bound to a197034c.
Local checks:116 focused tests plus2 subtests pass, including reference/source/
manifest rejection and workflow scope selection. The actual Ubuntu ZIP/native
bytes also verify. YAML, shell syntax, touched Python AST and diff checks pass.
Mac acceptance is pending; this submission has no performance/adoption claim.

### Following performance comparison (not executed by this job)

Reuse the immutable timer calibration harness at d24087ee and the existing
shop70 input: 50 shared-child reads and20 private-child writes; Go Pipe,
16MiB buffer pool/read1, cap=P+1, GOMAXPROCS8/GOGC100. Baseline is timer-adopted
main500020e7; candidate uses this guest with the same SDK/host runtime. Verify
source and generated identities before building and prove non-guest runtime
sources equal. Use six lifecycle pairs (8 Fresh/16 Fork per process) and five
complete-suite pairs each at P4/P8, alternating arms and parallelism order.
Warmups follow the existing timer-product plan (six separate processes).
Verification/timing/lock observers stay disabled. Retain every tail and report
paired wall/CPU, per-child p50/p95 and >100ms counts, plus SQL/cleanup results.
No speedup conclusion follows from correctness or from deleting outliers.
Record the exact measurement host/binary/guest and a fresh storage/time budget
before execution; Mac CI receipt comes first. No pgmem rerun, product adoption,
main integration, Qualification or release is included in this checkpoint.
