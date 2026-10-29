# Unreleased candidate changes

These notes describe source candidates, not a published version or release approval.

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
Required-host/minor P1 runtime/resource evidence remains pending; local controlled
owners are not full acceptance. No version, tag, Qualification or publication is implied.
