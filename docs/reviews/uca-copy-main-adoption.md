# UCA private-copy main adoption complete

The Human accepted the bounded optimization and its unfavorable P8 tradeoff,
then requested main integration before further PREPARE wait investigation.
[PR157](https://github.com/masahitojp/mariamem/pull/157) was squash merged on
2026-11-12 at `8df45792a927e440972266ee799d6f7223713e14`. Exploratory history was
not merged. Candidate head was `a8dd2f1ca3c7529b4e80f9f9e87a90b13055de3d`;
base was `500020e7dc6d702ef059f0e73a4bab738103b774`.

- [Canonical CI43190662084](https://github.com/masahitojp/mariamem/actions/runs/43190662084):
  two independent C builds; macOS15 arm64 and Ubuntu24.04 x86_64 regeneration,
  native SQL, UCA/lexer/CRC/worker/timer, Snapshot/reSnapshot and cleanup PASS.
  [Checksum-verified compact receipt](uca-copy-ci-43190662084/README.md) remains
  bound to `6da771df36fb452b920a3ae42e778ce110e46213`.
- Follow-up a8dd2f1c changes the stale-address image test, records and acceptance
  metadata only. Production runtime/guest/generator/workflow bytes are identical.
  The canonical run is reused on that basis, not relabeled as an exact-head run.
- [Development CI43201340611](https://github.com/masahitojp/mariamem/actions/runs/43201340611)
  passed at that exact candidate: check (job131125258891), integration
  (job131128491082), Live required gate (job131128531806). The earlier failed
  Development run retains its original failure and source.
- Immediately before merge, GitHub reported CLEAN/MERGEABLE. Required contexts
  were check, integration and Live required gate; strict base and enforce_admins
  were true. Merge matched the exact candidate SHA and used no admin bypass.

#154 is complete for bounded UCA adoption. At this checkpoint, #140/#156
retained the unresolved PREPARE tail; non-reproduction was not a fix.
Subsequently #156 completed the bounded pending-clear correction during output
integration; #140 retains the unproven natural sequence. See current
[project status](../project-status.md); this record starts no new investigation.
No new performance result, universal suite improvement, Qualification, release
or publication is claimed by this completion.
