# Issue133 bounded historical evidence cleanup

Decision: can the six historical public-source path failures recorded by C2 be
removed while retaining exact raw provenance, historical inventories and FAIL
contexts, and keeping current hash readers valid?

Base/source input: `a5ee1ed9cc2c6932d317fba77c339b364acd48df`. Scope is the six
files in `../issue65-p1-public/evidence/source-boundary.json`, their current hash
consumers, and focused preservation checks. Workload: source/JSON/text inspection
and Python 3.14 checks on macOS; no runtime/guest edits, builds, benchmarks or CI.
Ceilings: two hours active work, thirty minutes new tooling, zero heavy CI.
Exit: six path-only normalizations, reproducible raw/normalized SHA provenance,
reader trace, focused checks and full unchanged public-source guard PASS. If
any evidence cannot be preserved or reader classification is inconclusive,
stop with that gap and its next bounded action rather than relabeling history.

This is an intermediate result for #133, not completion of its local-dependency
inventory, formal clean reproduction or global cleanup. Parent #65 is unchanged.

## Result and raw provenance

All six files now contain one directory placeholder instead of the original
machine directory. Five `go_buildinfo` strings use `${HOST_BUILD}/wire.test` or
`${HOST_BUILD}/g2.test`; the original helper SyntaxError traceback uses
`${CHECKED_WORKTREE}/benchmarks/.../build_checked_guest.py`. The complete build
metadata after the binary name, traceback line number, source line, caret,
exception and disk figures are unchanged. No JSON reserialization was used.
No measurement, assertion, guest identity, binary/fixture hash or source
inventory entry changed.

[normalization.json](evidence/normalization.json) records each raw SHA256 and
normalized SHA256, byte counts and the raw source commit. Original raw bytes
remain retrievable from that commit and each original path, for example:

```sh
git show a5ee1ed9cc2c6932d317fba77c339b364acd48df:benchmarks/spikes/issue65-p1-owner/evidence/macos-reference.json
```

The base is existing pushed history, not an unpushed local ref. Raw files are
not duplicated into the public tree. [normalize.py](normalize.py) implements the
recipe: match exactly one directory in the named build-info or traceback
location, replace it with the corresponding placeholder and preserve every
other byte. It rejects missing/duplicate matches; it neither writes files nor
runs builds. The verifier requires the pinned base commit in local Git history
(fetch that commit if auditing from a shallow checkout); it compares raw and
normalized hashes and the exact output bytes.

## Hash readers traced before normalization

[reference-trace.json](evidence/reference-trace.json) records the full-path and
raw-hash references in all tracked text at the base, with line locations. Searches
for basenames, dynamic readers, shared hash helpers and workflow callers were
also inspected before changing evidence.

| Current reader | Handling |
| --- | --- |
| P1-owner `probe_baseline.py:21,201–207` | Update only `SOURCE_REFERENCE_SHA256` to normalized file bytes; guest/source/binary and source comparison checks stay fixed. |
| P1-timeout `probe_baseline.py:21,210–216` | Same single pin update. |
| Both `probe.py` modules | Import their baseline reader through `fix`; their separate `G2_REFERENCE_SHA256` pins read unchanged `macos-g2-result.json`, so remain unchanged. |
| Both `test_reference.py` modules | Verify the active baseline file pins plus guest/template/fixture and exact baseline-to-G2 inventory extension; unchanged tests pass. |
| Both owner/timeout workflows | Invoke these readers/tests from the tooling checkout and independently pin guest-source checkout; no workflow change needed. |
| `scripts/check_public.py` | Reads present public files and hashes current bytes. Policy and exclusions are byte-identical to base. |
| C2 `assemble.py`, `qualify.py`, `lifecycle.py` | Produce/read a newly staged product inventory and compare it to that product. They do not treat historical root source inventories as current checkout inventories. |

Historical P1-timeout inventories and the C2 `public-source.json` retain the
**raw** owner/evidence file pins. These describe the sources actually used then;
rewriting them would invent a different historical execution. They resolve via
the raw commit/path/SHA mapping above. The old core/public source-boundary FAIL
receipts and existing README/project-status FAIL descriptions retain their
original context. A current public guard PASS does not retroactively change
those results. No other raw-file hash consumers were found.

## Verification

Use `/opt/homebrew/bin/python3.14` for these local commands:

```sh
/opt/homebrew/bin/python3.14 benchmarks/spikes/issue65-evidence-cleanup/normalize.py
/opt/homebrew/bin/python3.14 benchmarks/spikes/issue65-evidence-cleanup/test_normalize.py -v
/opt/homebrew/bin/python3.14 benchmarks/spikes/issue65-p1-owner/test_reference.py -v
/opt/homebrew/bin/python3.14 benchmarks/spikes/issue65-p1-timeout/test_reference.py -v
/opt/homebrew/bin/python3.14 scripts/check_public.py
git diff --check
```

Focused preservation tests verify all six raw/normalized hashes and exact recipe,
all JSON fields outside build info, traceback context, active pins, historical
raw inventory references, every other existing owner/timeout/core/public evidence
file, and the unchanged guard. Negative cases reject a second application and
duplicate paths. The existing owner/timeout suites continue to verify source,
guest, fixture, G2 and workflow pins. No runtime execution is represented here.

## Remaining dependency and cleanup work

This resolves the six-path normalization checkbox only. A source-only scan of
current C2 assembly shows explicit `--guest-workspace`/`worktree` and
`temp/artifact` inputs at guest origin `be244a0bdb510a22417241c2aa2f76a9093aac1b`
with guest SHA256 `d4f30818c3410db186db5ef1c9abc5f14af0cdc52bb2b76bbca369e02eb1b481`.
The origin scripts, guest receipt/WASM, converter input manifest and installation
receipt must be regenerated or preserved together for #134, with remote source
availability and all input hashes verified. This task did not run that rebuild
or establish that all local-only required inputs are absent.

C2 also imports committed historical translation/adapter scripts and P1-b
binding/runtime/lifetime overlays; these are durable source dependencies that
#134 must formally place or retain, not disposable duplicate caches. Its
qualification/lifecycle scripts expect staged product/installed wheel and a
workspace venv. Environment/toolchain/cache inputs need the broader #133
inventory and #134 clean reproduction. No additional dependency was introduced
for runtime generation by this cleanup; the raw-history verifier is an audit tool.

Global classification of sibling checkouts, local refs, ignored inputs and
active caches, removal of finished owned outputs, deduplication decisions and
final >1GiB/debt audit remain with #133/coordinator after active owners finish.
No other worker workspace or shared cache was changed. This worker's generated
Python bytecode/public-guard output is removed after checks; compact receipts
and pushed Git history preserve the result. Orca workspace lifecycle remains
with the coordinator. The protected root user files were not edited or staged.

Final local results: preservation 5/5, existing owner reference 5/5, existing
timeout reference 7/7 and publication/extraction boundary 10/10 pass (27 tests).
`pytest` is unavailable in the requested Python interpreter, so the unchanged
unittest-based release-tools suite was run directly with that interpreter.
All four touched Python files parse. The full public-source check passes with
its original implementation; the final count and cleanup accounting are in
[validation.json](evidence/validation.json). No helper/skill implementation was
changed, so workspace-helper/runtime/release acceptance was not expanded.
