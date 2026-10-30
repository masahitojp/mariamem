# P1 prepared entry implementation approval

Human approved P1 implementation after reviewed design source_commit
`de860c4fc553907d237ad3a046ca6a6780ce0bb4`, conditional on the definitions below.
This decision is committed before the first P1 product/helper change. G1's prior
approval remains intact; main adoption, Qualification and release are separate.

- Existing None and callable preparation keep their meanings, including ignored
  callable return values. PrepareCommand is a new public class and the third
  accepted input. Other values still raise pytest.UsageError with the message
  `mariamem_prepare must return None, a callable accepting the preparation DB, or PrepareCommand.`
- Command env is an overlay on a copy of the parent environment at execution.
  Descriptor env is copied at declaration; overrides win except the reserved
  MARIAMEM_PREPARE_CONNECTION_INFO, which cannot be supplied in the overlay.
  The runner always replaces any inherited reserved value with the actual source
  connection JSON. Inherited PATH remains usable. This is deliberately not a
  hermetic environment: record relevant application inputs for reproducibility;
  do not print environment values or endpoint credentials.
- Retain at most 16 KiB of trailing stdout and 16 KiB of trailing stderr per
  command, while draining both streams throughout execution. Expose separate
  stdout_truncated/stderr_truncated flags and dropped-byte counts. Diagnostic
  rendering labels truncated output. Bounded retention applies to success,
  nonzero exit, timeout and interrupt; a full transcript is not promised.
- Child/routing cleanup failure stops subsequent dependent admission in that
  worker and preserves the cleanup cause. Ordinary assertions with successful
  cleanup continue to permit independent children. This is an approved visible
  behavior change; it is not a global pytest fail-fast or a stop of other workers.
- Document both public PrepareCommand and the admission behavior change in
  docs/python.md. Record the behavior change and public API in
  docs/release-notes/unreleased.md; no version/tag/ledger change is authorized.
- Update authorized_implementation_entries to ['G1', 'P1'] and scope_status to
  APPROVED_G1_P1_WITH_DJANGO_NONBLOCKING in
  docs/reviews/v06x-fixture-acceptance.json and scripts/check_fixture_design.py.
  Preserve G1's reviewed_design_commit; independently pin P1's reviewed design
  and this decision, with ancestry checks and negative mutations.
- Diagnostics describe command exit/status; quoted stderr is explicitly labeled
  application output, never an inferred cause. No shell interpolation,
  preparation-time framework routing, Django/Connector profile expansion or wire
  change. Keep readable-owned, original failures and honest cleanup state.

Required macOS15/Ubuntu and Python3.11/3.14 evidence remains a future acceptance
condition. Local macOS27.2/pytest7+9 characterization is not that matrix. P1
implementation may proceed; it does not by itself close P1 or overall dogfood.
