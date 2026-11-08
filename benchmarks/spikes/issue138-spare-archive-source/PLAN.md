# Bounded source diagnosis before analysis

Start: 2026-11-08T16:28Z, owner task84a871c28ac9, base e6ce0837e757cbf9075bb5534834df71e34ec182.
Question: why did the finite archiveON/dirty-threshold0/idle5s legacy case not
observe the positive spare_archive branch, and what smallest falsifiable next
case or observation is justified by exact source?

Evidence: exact MariaDB13.0.2 source620a4b5624222048fece7fe1789978ae0675cae2,
tag_object_sha308a50778fb4916ddde0d2923feea3d11dcc92c8 kept distinct; actual
legacy32c799031f619164d3730b61a0bc9d7ae48dcd9b/native4b3954a0faf42986459bc1ee68727be16d67bcbb
patch inputs, full-file pre/postimage inventories, previous raw marker failure
and matched archive PASS. Trace request production/consumption, archive lifecycle,
flush/wakeup/idle gates and exact wait adaptation. Classify facts/observations/
inferences/unknowns; do not infer branch hit from checkpoint or correctness from
coverage absence.

Exit: source-grounded answer with coordinates/hashes and strongest alternative,
one smallest finite next proposal with variables/events/initial state/markers,
route dependency and time/disk/binding costs, or precise missing files/evidence
and an inconclusive exit. Existing runtime FAIL/PASS and exit checkboxes remain
unchanged. No runtime/engine implementation, guest/host build, translation, SQL,
CI, benchmark, public or product adoption in this slice.

Ceilings: active45min including tooling10min, wall60min; source scratch2GiB,
free floor6GiB, temporary permission only, no global defaults. No helpers.
Use minimum official exact-commit files with matching known hashes; pinned archive
only if cross-file lookup requires it. All downloads/temp owned and guarded.
Preserve compact report/hash/coordinates, commit/push, remove only own recreatable
scratch and verify ignored/status/paths>1GiB/debt. Initial source checkout clean,
including ignored files; protected four parent files remain untouched.
