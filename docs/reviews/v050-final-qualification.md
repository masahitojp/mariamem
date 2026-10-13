# v0.5.0 final Qualification

**Final Qualification PASS** for source_commit
`bb637c49e6d6b50ec6761dead172a35f0b051f7e`.
[Run 38366609671](https://github.com/masahitojp/mariamem/actions/runs/38366609671)
used `operation=verify` and full qualification. Aggregate and both platform
guards returned `READY`. Product Validation remains pending; the next decision
is in [Human Review](v050-human-review.md).

## Identity and retained evidence

The workflow dispatch ran from main source
`3adf8cb50d63e5836826cfcf1c99745b1ad7383c`. The tested candidate was the separate
exact source above, not that workflow head. Candidate preparation follows the
completed J1 source `c427ed7619e07fae080037d7e254bb0cf5a0fb25` and changes only
version metadata, release-facing version examples and candidate notes.
The candidate's version is v0.5.0 / Python0.5.0, guest MariaDB12.3.3 and Wasm
`7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`.

The [receipt check](v050-final-qualification-evidence/receipt-check.json) records
artifact IDs and ZIP hashes verified against the GitHub API. The saved aggregate
READY replaces absolute runner home prefixes with `<runner-root>/` to preserve
the public-source boundary. Original and saved hashes are recorded separately;
identity review used the original bytes. Acceptance and qualification JSON bytes
are retained unchanged:
[aggregate READY](v050-final-qualification-evidence/ci-ready.json),
[qualification references](v050-final-qualification-evidence/qualification.json),
[macOS acceptance](v050-final-qualification-evidence/darwin-acceptance.json) and
[Ubuntu acceptance](v050-final-qualification-evidence/ubuntu-acceptance.json).
Acceptance hashes match READY; wheels match acceptance; all module and wheel
source-inventory hashes match Git blobs at the exact tested source. This is a
receipt/identity review, not a second local execution of the CI build or guard.
Later report commits do not inherit exact-SHA READY by relabeling this receipt.

## Results

| Boundary | Result | Evidence |
| --- | --- | --- |
| Two independent source→Wasm builds | PASS | [guest job](https://github.com/masahitojp/mariamem/actions/runs/38366609671/job/115193335111) |
| Independent Go regeneration and offline GPL source closure | PASS | Same guest job; READY binds build/regeneration identities |
| Native check/integration, canonical source and wheel build | PASS both OS | [macOS candidate](https://github.com/masahitojp/mariamem/actions/runs/38366609671/job/115199583440), [Ubuntu candidate](https://github.com/masahitojp/mariamem/actions/runs/38366609671/job/115199583655) |
| External Go default/Snapshot/failure/lifecycle, installed Python wheel | PASS both OS | Original acceptance receipts; no runtime override or checkout replacement |
| GORM32 / SQLAlchemy44 | PASS both OS | 32 / 44 cases per platform in acceptance receipts |
| Go1.27.2 consumer | PASS both OS | Same exact-source consumer; canonical qualification uses Go1.26.8 |
| Platform and aggregate source/license/provenance/artifact guard | READY | [aggregate job](https://github.com/masahitojp/mariamem/actions/runs/38366609671/job/115218157545), saved READY receipt |
| Product performance/resource comparison | PENDING | Human Review before the planned campaign |
| Publication and post-publication smoke | SKIP | Verify operation; those jobs did not run |

Actual consumer environments were macOS15.7.9 arm64 and Ubuntu24.04 x86_64.
The [existing J1 failure oracle](v050-join-lifetime-fix.md) and original R1–R5
scope remain the corrective judgment; passing ordinary integration does not
establish every schedule or full shared-memory race freedom. Mmap/assembly
detector observation limits and non-cooperative cleanup limits remain recorded.
No new correctness blocker was reported in this Qualification run.

Before release approval, compare the final candidate's user-visible time/resource
cost with released v0.4.7 using the existing paired scenarios. In particular,
assess startup tails, four-way parallel work, Fresh/Fork tradeoffs and cleanup
resource behavior. Old-guest saved Snapshots still require recreation; the
qualification does not weaken their identity checks or introduce migration.
