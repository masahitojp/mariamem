# EP1 / EG1 owned entry implementation checkpoint

For the consolidated evidence disposition and finite remaining acceptance, see
the [2026-10-30 acceptance map](e2e-entry-acceptance-map.md). The results below
remain historical checkpoints, not acceptance of later candidate SHAs.

The [pre-code decision](../decisions/e2e-entry-implementation.md) records the
Human's conditional approval and probe result before SDK code. Decision commit
`3ead1bc8d1ebb984f912cf4062c7a6dd759698c9` contains no product entry files;
`tests/test_e2e_decision.py` checks that ancestry and the recorded probe identities.

The implementation adds Python BrowserEntry/Config/case contexts and Go
mariamemtest.NewHTTP/Case(t). Both own preparation and source/baseline/Live,
register partial apps before readiness, reset exclusively before each case,
latch setup/cleanup debt and close app before DB owners. Python keeps original
interrupts and reports combined failures; Go preserves wrapped causes and cleanup
panic values. The Go lease survives t.Parallel/Fatal through t.Cleanup. Its client
tracks/cancels requests and closes owned response bodies before releasing a case.

No code from unmerged G1/P1 candidates is required. Preparation is a callback;
PrepareCommand reuse waits for that candidate's separate adoption. Callback/hook
work must be joined and physical SQL sessions retired by their owner. Deadlines
are cooperative. No guest/generated/Live semantics or mandatory SDK dependency
changes are included.

[Runnable source-build examples](../examples/e2e_owned/README.md) preserve the
existing fixed Django/Go orders application inputs. The existing Live workflow
adds component and actual-entry checks on both hosts and both Python minors,
retaining existing native/defect checks and required contexts. The publication
allowlist admits the new Go helper package.

## Verification boundary and remaining acceptance

Component controls cover partial preparation/start, original plus cleanup errors,
interrupt priority, cleanup attempt order, setup failure/admission latch, overlap,
Go parallel suspension/Goexit, HTTP body ownership and failure debt. These do not
prove every proposed finite failure/native/resource condition. Source-level
examples and workflow addition are not a claim that hosted execution completed.

Before full #18 acceptance: retain actual required-host/minor results for this
entry; complete exact-source installed wheel/external module consumer validation;
registered delayed-job and idle physical session hook controls; all partial Live,
Resume/external-state and concurrent/interrupted cleanup paths on the real
boundary; first-test/second-test/repeat and retained-baseline/resource/guard
campaign. Existing native fixtures qualify only unchanged inputs, not arbitrary
hook semantics. No full EP1/EG1 acceptance, main adoption, version/Qualification,
Product Validation or publication is claimed by this checkpoint.

Implementation evidence is recorded below after clean-source checks. Original
probe receipts remain bound to their actual source. Local macOS27.2 is not the
macOS15/Ubuntu acceptance matrix. The older parent of the design was reconciled
with main before product code, as recorded in the decision.

## Local verification at 7f3aaffb

Exact source_commit `7f3aaffb449506373a44780c19dd90d249a99290`, observed
macOS27.2 arm64 / Go1.26.10. Canonical check PASS:31 source checks, full Go
unit/vet,1251 Python PASS /51 explicit SKIP /82 subtests,5582 public files.
One existing unregistered shadow_maria marker warning is retained. The task
venv used Python3.14 / pytest9.2.0 with fixed routing dependencies.

Go helper and example compile/opt-in-skip race checks PASS. Actual owned Go HTTP
entry executes both orders cases against the real embedded MariaDB, restoring
seed and reusing UNIQUE input. The application binary's actual clean VCS stamp
matches this source. Python3.11/3.14 component controls each PASS13 cases;
pre-code decision checker PASS. The earlier focused Live/routing/workflow cohort
also passed164 tests and6 subtests during development, before final evidence.

[Assessment and raw logs](e2e-owned-entry-evidence/assessment.json) with
SHA256SUMS retain this exact source. Final evidence commits add records only.
Actual Python Django/browser entry is NOT RUN locally: its dependencies/browser
are selected in Live CI. The hosted matrix and remaining campaign above are
pending, not replaced by local component or Go results.
