# Unreleased candidate changes

These notes describe source candidates, not a published version or release approval.
They are staging notes: release preparation manually transfers applicable items
into the versioned `release/NOTES-*` file and checks them against adopted code.
The release workflow does not consume this path automatically; see the
[notes handoff](../releasing.md#next-release-notes--python-minimum-and-application-test-entry).

## Python prepared entry (P1)

- New public `mariamem.PrepareCommand(argv, *, timeout=120, cwd=None, env=None)`
  is a third preparation input beside None and a callback. Existing callable
  return values are still ignored. Unknown values remain pytest UsageError.
- A child or routing cleanup failure now blocks subsequent dependent tests in
  the same worker. Ordinary assertion failure with successful cleanup still
  allows the next independent child. Other xdist workers remain independent;
  this is not global pytest fail-fast. Explicit fixture overrides own their boundary.
- Command env overlays the parent environment, then the actual preparation
  connection JSON replaces the reserved variable. This is not hermetic execution.
- stdout/stderr are continuously drained with a trailing 16 KiB retained per
  stream; truncation flags and dropped-byte counts are explicit. Timeout and
  interrupt attempt bounded termination/reaping of the owned process group.
- Error notes and a final entry summary supplement ordinary pytest reports.
  Application output is labeled as such; no application root cause is inferred.

See [Python usage and compatibility](../python.md#prepared-command-entry).
P1 follows the [fixed exit](../decisions/p1-fixed-exit-v060.md): entry lifecycle
correctness remains required; detailed resource characterization is deferred to
v0.7.x. The fixed-profile candidate has passed both-host/minor acceptance; main
adoption is recorded by PR #26 merge4a8a6835. Controlled owners are component evidence. No version, tag, Qualification or publication is implied.

### Owned E2E entry candidate (not adopted)

Adds Python `mariamem.e2e.BrowserEntry` and Go `mariamemtest.NewHTTP/Case(t)`:
preparation once, exclusive sequential Live reset/admission, fresh browser context
or owned HTTP client per case, partial-app cleanup registration and stop after
setup/cleanup debt. These are source-build candidates pending full #18 acceptance
and main adoption. No published version, guest or wire contract is changed.
