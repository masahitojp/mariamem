# Bounded routine adoption — native CI receipt

2026-10-20. **Both native platforms PASS the added DEFINER boundary.** The
previously pending Ubuntu confirmation is closed. This adds evidence to the
already approved adoption scope; it does not approve a new scope or establish
that the canonical product candidate is complete.

[Run39389127237](https://github.com/masahitojp/mariamem/actions/runs/39389127237)
passed on exact source `387a5f2a685748877d17e706491738ae242c0c4b`:
guest118516115003, Ubuntu118519232548, macOS118519232587.

| Gate | macOS arm64 | Ubuntu x86_64 |
| --- | --- | --- |
| Source/schema/mode/lifetime binding checks |55 PASS |55 PASS |
| Normal guest translation/host build/SQL smoke |PASS |PASS |
| Existing routine/isolation/rejection/cleanup runtime suite |8 PASS |8 PASS |
| Bounded DEFINER:16 Fresh combinations,48 calls including two Forks |PASS |PASS |
| Default Connector/Python26.7.0 |PASS, CMySQLConnection |PASS, MySQLConnection |
| J1 heap/mmap failure/protection oracles |Expected negative failures; protected PASS |Expected negative failures; protected PASS |
| Go failed-start and lifecycle resources |9 mappings created/released; final zero active |9 mappings created/released; final zero active |

The complete raw native artifacts are preserved losslessly in the
[evidence index](v06x-routine-adoption-bounds-ci-evidence/files.json), with
original/stored hashes and bytes. The [structured receipt](v06x-routine-adoption-bounds-ci-evidence/summary.json)
binds source, guest/host hashes, environments and result counts. No paths were
normalized. Both regenerated hosts report guest SHA256
`118ef83ee066d57f946603f7e2a2b2c60d9b5f1cd4d627c3d18a73cbd963350c`.

Both platforms retain DEFINER/SQL SECURITY metadata and the same observed results
across Fresh and two children. Their guest reports `@@skip_grant_tables=1`;
CURRENT_USER/USER remain root@localhost in this cohort, including the absent
explicit definer. This is not grant enforcement or native authorization
compatibility. The earlier ordinary native control's two1446 rejections remain
separate evidence; the control was not re-run in this CI.

Packages/package bodies remain outside product support, compatibility testing
and guarantees; no package execution tests were added. Their enum values remain
unchanged in mysql.proc. Events remain excluded by the embedded build restriction;
the existing runtime suite checks1235. These are the unchanged
[approved scope](../decisions/routine-support-scope.md).

**Remaining:** minimal canonical source/generated artifacts/provenance/inventory
promotion and the separately recorded prepared/text-result production acceptance
conditions. The experiment is not merge-ready as a whole. Version placement,
main integration, final Qualification and release remain separate decisions.
This candidate workflow is explicitly UNQUALIFIED, not a release READY result.
The [earlier bounded report](v06x-routine-adoption-bounds.md) remains a historical
local-evidence cutoff; this receipt supersedes only its pending native-CI state.

This follow-up changes documentation/evidence only. Its later commit is not
relabeled as the tested candidate SHA. Runtime tests were not re-run locally for
these documentation edits.
