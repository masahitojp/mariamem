# Routine adoption scope and bounded DEFINER check

2026-10-20. **Scope recorded; macOS DEFINER check PASS. Ubuntu DEFINER confirmation
and canonical production promotion remain outstanding.** This report does not
claim completion of the canonical adoption candidate. It closes the requested
scope wording and the local bounded SQL question while submitting the same
bounded probe to both native CI jobs.

The Human approved proceeding with minimum routine adoption preparation, then
fixed the boundary: **procedures/functions IN; packages OUT without tests or
support guarantees; events OUT by embedded restriction; DEFINER bounded**.
The [decision](../decisions/routine-support-scope.md) owns that scope. This is
not a new ask to re-approve the same boundary. Version placement, main
integration, Qualification and release remain separate decisions.

## Confirmed results

| Check | Result | What it establishes |
| --- | --- | --- |
| DEFINER matrix on macOS arm64 guest | PASS,16 combinations | Omitted/CURRENT_USER/explicit root/nonexistent definer × DEFINER/INVOKER × procedure/function: CREATE, execution, SHOW CREATE and routine metadata |
| Same16 definitions and results in two Forks | PASS |48 total calls, including Fresh; exact metadata/execution equality across children and the original baseline. Current-user behavior is recorded, not declared generally equivalent to native privileges |
| Native MariaDB12.3.3 comparator |14 execute;2 expected account rejections | Same pinned source revision with normal grant tables; both missing-definer SQL SECURITY DEFINER calls reject1446, whereas the guest executes them |
| Native context vs guest context | Difference confirmed | Guest CURRENT_USER/USER remain root@localhost in these cases, even when metadata names absent_owner@example.invalid. Native uses the real authenticated/definer account contexts |
| Post-error connection health | PASS |SELECT19 succeeds for every case, including native's two account rejections |
| Formal development generation/build/SQL smoke | PASS | Reused exact CI-built guest through strict origin verification, fresh translation/installation/host compilation and standard SQL smoke |
| Ubuntu DEFINER cases | PENDING | New probe is added to each native candidate-CI job, after existing runtime acceptance; no local PASS is inferred |
| Package behavior | NOT TESTED, intentionally OUT | No CREATE PACKAGE, PACKAGE BODY invocation or package-compatibility test added. Exact enum/signature validation is not package behavior coverage |
| Events | Existing restriction unchanged | Previous both-OS runtime gate asserts1235; no event implementation or scheduling test added |
| Canonical adoption / Qualification / release | NOT DONE | Canonical guest/release artifacts are not promoted by this documentation/test follow-up |

The guest's `@@skip_grant_tables` is1; the native control's is0. This comparison
intentionally makes the user-visible limitation concrete. It is **not** a claim
that the two environments have equivalent authorization settings, nor evidence
of a Wasm-to-Go translation defect. Explicit clause and metadata retention can
support ordinary routine-bearing migrations/dumps without promising account or
privilege tests. A migration relying on native account existence, CURRENT_USER
context changes or grant enforcement needs the appropriate real-server check.
No definer text is stripped, rewritten or silently replaced in storage.

## Exact evidence and ownership

[Summary](v06x-routine-adoption-bounds-evidence/summary.json) and
[lossless raw evidence index](v06x-routine-adoption-bounds-evidence/files.json).
The final assertion-bearing owner is
[tests/v06_routine_definer_probe.py](../../tests/v06_routine_definer_probe.py).
An initial observational pass is preserved separately from the final asserted
pass. The final probe checks successful rows, explicit definer/security metadata,
SHOW CREATE and exact retained child results, not only command exit status.

- Host/generation source: `d3eef9e031a7a64a7bbbd8b9e49a866207dd8c29` (commit
  identity inspected before generation).
- Guest source receipt: `2c599bb904e3d523585347ccefc57ee1d833a993`, downloaded
  from successful candidate CI39379752111; input/source/patch hashes were
  verified by the existing development route. No origin policy was widened.
- Guest SHA256: `118ef83ee066d57f946603f7e2a2b2c60d9b5f1cd4d627c3d18a73cbd963350c`.
- Regenerated host SHA256: `1eb79b527c16ade9001f60b9a451021c703214d745357c4366e0bad6e4c95b2b`,
  byte-identical to the prior macOS candidate-CI host. Go1.26.8; Python3.14.8;
  PyMySQL1.2.3. No Connector/Python DEFINER matrix is claimed here.
- Native control: image digest and actual source revision are in
  `native-identity.json.gz` (MariaDB source83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e).
  Its fresh datadir was a disposable tmpfs. The container was stopped/removed.

No guest/converter/runtime owner changed for this follow-up; no generated Go
was edited. Existing ordinary lifecycle, J1 and Connector evidence remains the
[exact earlier both-OS CI cohort](v06x-routine-bootstrap-ci-review.md), not a
claim that today's local probe re-ran those tests. Candidate CI will bind its
new source and run the added bounded probe alongside the unchanged existing gates.

The initial workspace command failed before generation because its launcher path
was relative to the caller rather than the helper's worktree cwd. That failed
attempt is not counted as generation evidence; its small helper receipt is
retained locally. The successful run used an absolute launcher path.

## Reproduction and boundary to production

For the final bounded check, use the explicit host produced by the normal
UNQUALIFIED development route:

```sh
PYTHONPATH=/absolute/dev-output/product/python python tests/v06_routine_definer_probe.py \
  --host /absolute/dev-output/mariamem-dev-host --output /absolute/definer.json
```

The normal development output and exact source/guest records must pass existing
origin guards; do not replay a stale guest across changed build inputs. To replay
the local generation cohort, create a clean checkout at the host source above,
prepare a disposable workspace with the same budget, and copy the preserved
`local_campaign.py` into its `temp/campaign.py`; it uses that checkout's normal
regenerator. Copy `initial_probe.py` into `temp/definer_probe.py`. The preserved
`native_control.py` expects the same layout and Python venv. It creates a new
named container, never replaces another, verifies the native source revision,
and stops it in finally. This is diagnostic comparison, not a benchmark.

**Remaining canonical work:** produce the minimum production source patch and
formal generated artifacts/provenance/inventories, with the separately decided
text-result prerequisite. The exploratory prepared implementation has unapproved
limits/production acceptance conditions listed in the
[prior review](v06x-prepared-multi-spike.md#conditions-for-production-and-review-limits);
this routine scope decision does not silently approve or merge them. Preserve
failure oracles, strict source/guest identity, and public exclusions. Do not call
the exploratory branch merge-ready. No main integration or publication is done.
