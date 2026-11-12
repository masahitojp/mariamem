# CI43318436823 repair verified locally

Both native jobs failed the Python portion of daily checks with the same9
failures before integration. Canonical guest two-build equality, independent
120-file regeneration on both OSes, generated build guards and20 negative
evidence controls passed at `ad7deda13ef205774af34c152dd531c85c02782c`.
The run remains FAIL; its successful earlier stages are not runtime acceptance.

Three causes account for the nine failures:

- Missing SQLAlchemy/pytest-xdist in the candidate workflow (six tests).
- Shallow checkout omitted the pinned wire source commit (two tests).
- The integration selection test still asserted the old literal filter (one test).
  Local daily had passed before the selector changed; the later focused check
  did not include this existing selection test. That verification gap is corrected.

The workflow now uses the normal Development unit dependency list and complete
native-job history. The selection test checks that both WorkerTrap and
DictionaryWait actual-guest tests match. No check is skipped or weakened and
no runtime, guest bytes or benchmark inputs change.

[Failure receipts](failure.json) bind both downloaded artifacts and all failures.
[Local verification](verification.json) uses a fresh Python3.14 environment with
the workflow's exact dependency arguments: the134 focused tests pass, followed
by the complete Python-only check, including a pass with CI's default parent
plugin autoload. YAML and all embedded shell steps parse; the public-source
and diff checks pass. A new full canonical CI run is still required and will be
submitted once; no main integration or release is authorized here.

## Recorded scope before implementation

Question: can the authorized installed candidate reach both-platform integration
with the normal daily-check prerequisites and the updated test selector?
Bounded evidence: both native artifacts, their exact source/hash receipts,
all nine failed tests, a fresh Python3.14 environment using the workflow's
dependency command, and the ordinary Python-only check. Exit: those tests and
configuration checks pass, then submit one canonical verification run and hand
off. No runtime changes, guest build or benchmark locally. No new measurement
tooling; at most30 minutes diagnosis/repair verification and one heavy CI
submission. If another runtime/correctness issue appears, retain the failure
and report the missing evidence instead of widening the change.
