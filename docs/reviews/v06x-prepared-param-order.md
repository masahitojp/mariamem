# P2 unsigned/NULL descriptor order — source repair candidate

[CI39601636017](https://github.com/masahitojp/mariamem/actions/runs/39601636017)
at source_commit e8f5f765b091347db21e55629e1ae7859afd9f3c passes formal
generation/compilation/smoke, installed identity/mutations, P1, original22,
TIME13 and additional20 native comparisons on **both OSes**. The former eight
failures no longer reproduce in those20 controls. The final added15-case gate
fails seven unsigned-NULL metadata cases; this is a real remaining mismatch,
not a harness failure or an accepted exception. P2 remains incomplete.

Continue within the approved parameter-binding repair scope. Fix the descriptor
attribute at its source; do not mask output flags or change native expectations.
[Receipt and captures](v06x-prepared-param-order-evidence/receipt.json) record
the exact boundaries and pending gates. This does not request main adoption or
release, and does not expand into unrelated engine behavior.

## Observed user impact

All15 scenarios return successfully and have healthy following SQL on both OSes.
The seven differences occur in first-NULL and reused-NULL executions with the
unsigned descriptor bit set. Fourteen column packets differ in exactly the
UNSIGNED_FLAG bit0x20: guest omits it, native includes it. Binary values, result
termination/status and following SQL match. The signed seven cases and the
grow/shrink counter case match native completely. There is no observed timeout,
crash or wrong row value in these15 captures. Driver/ORM misinterpretation is a
possible consequence of inaccurate metadata, not a reproduced consumer failure.
No data corruption is inferred from this metadata difference.

Source and Ubuntu unit jobs PASS in the single metadata read. macOS unit had
no conclusion then and is not asserted PASS here. Both runtime artifacts are
complete and fail specifically the15-case differential step. This report does
not turn the overall run green because preceding gates pass.

## Cause and bounded correction

Pinned MariaDB83e909fc's
[embedded parameter functions](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_prepare.cc#L1188)
call setup_conversion before assigning unsigned_flag, and assign it only for
non-NULL values. By contrast,
[ordinary set_conversion_functions](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_prepare.cc#L1132)
assigns the descriptor attribute first. NULL cannot repair the stale attribute
through a value conversion. The captured missing flag agrees with that source
path. Non-NULL handler selection can also see a previous attribute; actual wrong
numeric values have not been reproduced by these captures.

In guest/experimental.patch, assign client_param->is_unsigned to unsigned_flag
before setup_conversion in both emb_insert_params and emb_insert_params_with_log,
guarded by __wasi__ inside the existing embedded-only region. Retain the existing
non-NULL assignment; its repeated same-value write is harmless. Both paths now
use the current descriptor for NULL and handler setup. No type rename, SQL retry,
public API change, canonical source.patch edit or converter change is introduced.

The exact full SQL pre/postimage and combined patch hashes are updated in
guest/prepared_source_patch.json. The existing TIME hunk remains byte-identical;
its old intermediate postimage is recorded separately. The libmysql repair and
its portability-after preimage are unchanged. Preparation verifies the new
source-function extracts against the complete source as well as its hash, with
zero-fuzz application and repeated/changed-input rejection.

## Verification and next gate

- **PASS:102 local checks on macOS arm64.** Before/after real extracted functions
  with mock dependencies test both execution paths, NULL/non-NULL and both flag
  directions: before0/8, WASIX after8/8, non-WASIX unchanged0/8. Address/undefined
  sanitizers and conversion-error propagation controls pass. This proves source
  assignment order under the mocks, not complete engine semantics.
- **PASS: full-source application in the formal relevant-file order**, including
  fixed portability, unchanged TIME hunk, both updated parameter functions,
  unchanged libmysql postimage and repeat rejection. Existing lifetime/identity/
  source-owner/tooling controls and canonical inventory/public checks pass.
- **PASS: unchanged15 native cases replay.** No old expected fixture changes.
  Two extra native controls cover uint64 max/signed min and text, unsigned↔signed,
  NULL/non-NULL and descriptor reuse; both have exact saved references and replay.
  Native remains the pinned Linux arm64 container on macOS, not a guest PASS.
- **PASS: source build and both-OS unit preflight** at a342f30 in
  [CI39607505031](https://github.com/masahitojp/mariamem/actions/runs/39607505031).
  Runtime was SKIP by source-branch design, not a runtime PASS.
- **PASS: new guest identity review.** The [binding receipt and reproduction](v06x-prepared-param-order-binding/reproduce.md)
  cover guest4dad84d0, fixed converter/13 patches, exact lifetime bodies, all
  data/TLS and the full memory-initialization function. Local103 checks PASS.
- **PENDING: actual both-OS runtime gate**, unchanged P1/22/TIME13/20/15 plus the
  extra2, now submitted through prepared-product with that single binding.
  P2–P6, independent canonical generation, main adoption and release remain open.

Reproduce with the fixed pins and Python3.14/pytest8.4.2/PyMySQL1.2.3: run
tests/test_prepared_param_order.py plus the eight focused owners from the
[prior binding recipe](v06x-prepared-p2-repair-binding/reproduce.md). Build the
source normally; never edit generated Go. New native control command:

```sh
python tests/v06_prepared_unsigned_probe.py --native-port PORT \
  --reference tests/fixtures/prepared-unsigned-native.json --output unsigned.json
```

The existing15 command/reference are unchanged. CI adds the2-case probe after
them. Saved raw JSON, file hashes, patch application and local output are under
v06x-prepared-param-order-evidence. The initial local C++ harness compile lacked
C++ standard headers; the harness now uses C headers and built-in language arrays,
and all six source-function/sanitizer variants pass without a skip. No compiler
or product toolchain update was made. Scratch/venv/container cleanup is separate
from these correctness results.
