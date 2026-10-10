# v0.4.5 public smoke recovery — approved implementation

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

## Approved bounded recovery

The maintainer approved this recovery. The existing workflow now provides the
advanced `public-smoke-recovery` operation with one read-only Ubuntu job and no
dependencies on qualification/publication jobs. Normal `verify`/`release` paths
are unchanged. Source verification and artifact transport reuse existing helpers.

Focused tooling/identity/consumer tests: 120 passed in 6.11 seconds. Workflow YAML
was parsed and its read-only, dependency-free recovery boundary checked. The
original publication was also authenticated with the actual helper against
GitHub: artifact `11657378044`, ZIP SHA256
`bff47a5acc2842d82e01c5a5711abb8227cdf74c8eebf417db8f961c03211abe`.
Native corrected Ubuntu smoke passed in
[recovery run 38021032245](https://github.com/masahitojp/mariamem/actions/runs/38021032245),
job `114121843802`. Published source is `d992e26a6d110ceeb54f69d71acd1358c72abb1b`,
program source `973a6741876052ff9d8ca7374bee11436ad88d37`, and tooling source
`135b791e3153cf02081b053337ec298a16e0c7ae`. Both public Go and installed-wheel
smoke passed; runtime cache inventory was empty. The accepted Ubuntu wheel hash
remained `aa5ddc7e96e7a28f380b791d9b52a19a800d73d2329a4adbedd41316a75a0d0f`.
All build, qualification and publication jobs were skipped in this recovery.
No local full runtime qualification or release rebuild was performed.

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

## Decision and remaining gate

Approved: smoke-only recovery extending the existing workflow, preserving
separate published-source, repaired-program and tooling identities. The actual
program source is `973a6741876052ff9d8ca7374bee11436ad88d37`; subsequent tooling
and report commits are not used as the program source because their diff includes
other files. The workflow validates this distinction mechanically.

Final status: v0.4.5 published; macOS public smoke passed in original release run
`38014576300`, and Ubuntu public smoke passed in separate recovery run
`38021032245`. The original failed run remains failed; it is not relabelled.
The repair and recovery tooling remain on their dedicated branch, not main or
the published tag. No API/runtime defect was demonstrated by this failure;
it demonstrated a smoke precondition violation.
