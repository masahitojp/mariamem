# Dump reader maintained-CI handoff

The Human requested the adoption review's CI follow-up. This change implements
the trigger and source-binding work; it is not main integration or host adoption.
The earlier [adoption review](v06x-dump-reader-adoption-review.md) and
[07c9d7e receipt](v06x-dump-reader-evidence/ci-40207664068/assessment.json)
remain under their original source and decision context. The revised workflow
needs its own exact-source CI result before this gap is considered verified.

## Selection and execution

The dump workflow selects relevant pushes to main and the candidate experiment
branch, plus pull requests targeting main. Dependencies include the stable
migration owner, dump acceptance/tests, Python package, all host/generated/guest
inputs, top-level Go files/module pins, release inputs and build/identity scripts.
Manual dispatch remains available. Documentation-only changes do not launch the
matrix. The workflow uses the default checkout and GITHUB_SHA throughout: for a
pull request this is the tested merge commit, not a different head-only override.
It uses read-only contents permissions and never pull_request_target.

Tests cover required trigger/path selection and negative removal of the PR
trigger, main branch, migration/runtime/SDK/script path coverage. They enforce
the workflow's simple explicit syntax; actual GitHub event delivery is established
only when that event occurs. This change does not claim branch protection has
been configured or that an actual main/PR run has already happened.

## Continuing identity versus historical approval

`bind_input.py` schema2 binds the exact clean current source commit and Git tree,
rechecking identity after reading the inputs. It no longer constrains future
committed runtime changes to the experiment's six-file difference from its old
origin. Host changes must pass the current runtime/differential tests rather than
being rejected solely for changing an old hash.

The historical three-file correction's before/after hashes are preserved verbatim
in [the host delta record](v06x-dump-reader-host-delta.json). Moving this record
out of the test allowlist does not approve the host correction or edit old CI
archives. The producer's original SHA256 is pinned directly, so normal checks
no longer need the unrelated experiment-origin Git object to be fetched. The
canonical dump, original manifest, migration inputs, producer options and fresh
candidate production still must match exactly.

Both campaign and interpreter runner retain `source_identity` and
`verify_go_binary`; the installed packaged host hash is still checked against its
wheel manifest. Wrong/stale binary source, dirty builds, wrong compiler and
missing/duplicate identity remain rejected by `tests/test_git_identity.py`, now
included explicitly in the dump workflow's focused steps. Whole saved binding
comparison rejects changed source/tree/product hashes and stale producer receipts.
No SQLSTATE, framing, child isolation, cleanup or no-admission oracle changed.

## Local verification and limits

Python3.14:109 tests and37 subtests PASS across dump helper, differential assessor,
workflow selection, current/canonical binding, native acquisition and Git/binary
identity owners. A temporary Git repository proves that a new ordinary committed
runtime file is allowed without experiment history; dirty tracked/untracked
files, old SHA, annotated-tag object and abbreviation are rejected. Source changes
during binding and saved receipt mutations are negative cases. YAML parsing and
diff whitespace checks PASS. No runtime/API/guest/generated/release input changed.
These are focused local checks, not a new installed-wheel or native matrix PASS.
CI remains responsible for the revised candidate's full execution. No local
runtime suite or xdist census was repeated for this tooling/workflow change.
