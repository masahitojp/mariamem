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
