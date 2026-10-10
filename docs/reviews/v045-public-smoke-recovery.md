# v0.4.5 public smoke recovery — Human Review

## Observed failure

Release source `d992e26a6d110ceeb54f69d71acd1358c72abb1b` was published by run
`38014576300`. Final artifact qualification and publication succeeded; macOS
public smoke succeeded. Ubuntu jobs `114116699819` and `114118291199` both failed
in the public Go program at `main.go:37`, before Python public smoke:

```text
panic: mariamem busy: handshake, query or session cleanup is active
```

`sql.DB.Close()` closes client connections but does not wait for server-side
COM_QUIT cleanup. Existing consumer tests explicitly call `WaitDisconnected(ctx)`
before Snapshot. The narrowed public smoke omitted it. The same uncorrected job
was retried once; that retry did not validate the fix and failed identically.
No further uncorrected retries are justified.

Repair `973a674` on `fix/v045-public-smoke-session-drain` adds the existing
`db.WaitDisconnected(ctx)` call before Snapshot. No runtime, wheel, guest,
provenance, tag or published asset bytes change. Formatting/diff checks passed;
the corrected program has not yet been executed on native Ubuntu.

## Why ordinary rerun cannot apply the repair

The current `public_smoke` job checks out `needs.resolve.outputs.source_sha`.
Rerunning it therefore always uses the published candidate's old program, even
if main or another branch contains the fix. Republishing a version, moving its
tag or rerunning build/artifact qualification is not an appropriate remedy.

## Proposed bounded recovery, not implemented

Extend the existing Release workflow with an explicit advanced smoke-only
recovery path. Keep normal `verify` and `release` operations unchanged. Do not
add a competing workflow, acceptance framework or new release version.

Recovery inputs must distinguish:

- published source: full immutable `d992e26a6d110ceeb54f69d71acd1358c72abb1b`;
- original publication receipt: run `38014576300`, authenticated successful
  publication job and artifact ID/hash;
- corrected smoke source: a full immutable repair commit and program hash.

Keep the accepted candidate checkout intact. Allow only the corrected external
Go smoke program to be supplied to existing published-mode acceptance. Before
execution, mechanically require the repair's only source difference to be
`scripts/guest_smoke/main.go`; reject runtime/library, identity-validation,
artifact-contract or other harness changes. Bind the actual supplied program
hash into the recovery report; never label it the original tested harness.

Retain existing publication proof checks, downloaded asset SHA256 checks,
public Go tag origin and library-file identity, installed-wheel identity and
minimal Go/Python SQL/Snapshot/Fork/Close smoke. Fail closed for missing,
expired, mismatched or unauthenticated original proof. Run only Ubuntu because
its public smoke is the remaining failure; preserve macOS's original result.

The recovery path must have read-only repository permissions, no publisher/tag
steps, and no build/runtime/artifact qualification dependency. It must emit a
separate recovery receipt; do not overwrite or relabel the failed attempt or
claim that original Release CI passed.

Focused verification before submission: bad source/tag/receipt/program identity
rejection, forbidden repair-file rejection, no publication/build execution,
and actual program handoff. Native Ubuntu smoke then validates the published
distribution with the corrected harness. Broader runtime acceptance has no
concrete dependency on this repair and is not required.

## Human decision

Approve the smoke-only recovery extension to the existing workflow, preserving
separate published-source and repaired-harness identities? This changes an
execution boundary and therefore requires review before implementation, under
the approved v0.4.5 rule for material evidence-model changes.

Until that decision and successful recovery, status is: v0.4.5 published,
Ubuntu public smoke incomplete. No API/runtime defect is demonstrated by this
failure; it demonstrates a smoke precondition violation.
