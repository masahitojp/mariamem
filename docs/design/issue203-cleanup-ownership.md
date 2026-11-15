# Close cleanup ownership (#203)

Parent: #119. This is an isolated implementation candidate, not adoption or
release approval. Baseline source_commit:
`ca7b42fb64aa35aefe717412b625e2d32bab7ca4` (git_identity inspected).
Changes since the design baseline b652b53a were distribution/docs only.

## Internal contract for #204 and #205

`Process.Done()` means the runtime cleanup attempt and transport join ended;
it is not a resource disposal success signal. `Process.RetryDisposal(ctx)` waits
for Done and retries only `disposal.Owners(exitErr)`. Execution failure alone
is not cleanup debt. The stored original exit/operation error remains immutable.

`Server.DisposalComplete()` is true only after runtime cleanup owners and host
session workers have completed and transfer removal succeeded. Database's
existing temporary removal/lease settlement follows these dependencies.
Normal pending async cleanup is not introduced here. #204 must keep its lease
without calling TrackCleanup until an actual uncertain cleanup failure occurs.

`disposal.Owner.Done()` closes only on successful reclamation. An operation's
completion/result must remain distinct (#204/#205). Retain starts the existing
single background continuation; it is not an infinite retry loop. Explicit retry
is serialized by the owner. Failed operation errors remain failed even when a
later reclamation succeeds.

## Resources and failure ownership

| Resource | Initial owner and release | Failure / retry contract |
| --- | --- | --- |
| Guest memory | runtime, after every worker joins; release closure | retainRelease preserves closure in Owner; retry invokes the same idempotent memory mapping owner |
| Prepared mappings | PreparedFiles, after guest and descriptor teardown attempt | Close retains failed mappings only; successful mappings are never retried; runtime/constructor error retains owner |
| Logical descriptors | WasiStubs, after guest join, excluding caller-owned stdio | DescriptorReleaseError retains failed objects; no blind re-Close of an uncertain native FD; conservative unresolved debt |
| Peer pipes and response reader | linked adapter | existing joined-completion boundary retained; early stop belongs to #205 |
| Transfer directory | Server disposer | waits for runtime resource owners plus host workers; RemoveAll retry remains owned |
| Database temporary directory | Database removeTemporaryAfter | depends on server cleanup; original result and owner retained |
| Fork lease | Database / forklimit | retained through uncertain cleanup; returned after all dependency owners complete; existing admission recovery rules retained |

Generic File/net.Conn/net.Listener Close errors do not provide a common proof
of whether the underlying resource remains open. The error object retains each
failed wasiOpen, including its concrete resources. A second CloseDescriptors
call does not re-close it or resolve that debt. The runtime retained owner keeps
the error reachable and reports it on retry. Typed recovery for such errors is
not supplied; it must establish safe semantics before it can clear debt.

Prepared-file construction failure also retains partial mappings through
closeOwned, rather than dropping the only reference when returning nil.

## Generation and attribution

The canonical prepared-file template is
`benchmarks/spikes/generated-go-integration/prepared-files.go.txt`.
Its output is reproduced with the existing runtime_memfs.apply_mapping installer
adapter and gofmt; only code/base/prepared_files.go changes in the generated
inventory. Runtime/descriptor/owned-prepared adapters remain in the installer's
HANDWRITTEN_FILES boundary. No translated SQL engine function, converter patch,
guest bytes, or input manifest changes.

layoutgen is run against this runtime to reproduce image/layout.json. Its source
hash changes, but initial memory and the static envelope stay the same.
Static-image staging now copies the disposal helper required by the adapter.
Provenance and license continuity record the exact helper before/after hashes;
the original retained-function audit identity is preserved. This continuity
proposal remains part of the candidate's integration review, not a new binary
symbol audit or qualification claim.

## Verification boundaries

- Base tests inject mapping failure, verify only the failed mapping is retried,
  and retain a failing descriptor without calling Close twice.
- Runtime tests inject a release closure failure and verify owner retention,
  successful retry and preservation of the original error.
- Host's controlled runtime-completion test sends retained debt through the
  actual guest transport adapter, host disposer and Fork lease. It checks Done
  with unresolved resources does not permit disposal/transfer deletion, and
  later recovery permits disposal and returns the lease. The completion error
  is injected; this is not an actual guest OS munmap failure reproduction.
- Root/fixture unit tests cover existing disposal contracts. No new async API,
  performance campaign, opposite-platform qualification or release is claimed.

For handoff, use this candidate's commit as the common base. #204 consumes
RetryDisposal and keeps operation-result completion separate from disposal;
#205 must preserve the existing Done/exitErr publication ordering while adding
a separate stopped boundary. Do not weaken worker join or Snapshot/export.
