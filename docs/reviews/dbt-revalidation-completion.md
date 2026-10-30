# Issue19 fixed dbt1.7 repair revalidation — both hosts confirmed

2026-10-31 JST. **The original TEXT DISTINCT dbt failure is resolved for the
fixed dbt-mysql1.7.0/core1.7.20 workload on observed macOS arm64 and native
Ubuntu24.04 x86_64.** The original question is answered; no further repair or
measurement is needed for this replay. Keep the EOL adapter/core and exact
consumer/platform limits visible; this is not general dbt support or release
qualification. The separate1.8 adapter/unit-test experiments do not extend this
completion condition.

## Source-bound results

| Observation | Executed source_commit | Result |
| --- | --- | --- |
| Local macOS27.2 arm64, Python3.11.18; native SQL reference amd64-emulated | `f37b2a7b86b7187613edc99c6aac069eef5071ac` | native/guest × threads1/4 PASS |
| CI Ubuntu24.04.5 x86_64, Python3.11.17; native amd64 SQL reference | `7a9a6f72dc83bc7d9f1526fa9704d32bbcefc126` | native/guest × threads1/4 PASS |

[Ubuntu run41089916368](https://github.com/masahitojp/mariamem/actions/runs/41089916368),
[job124180806793](https://github.com/masahitojp/mariamem/actions/runs/41089916368/job/124180806793),
artifact12993587783. Original ZIP SHA256
`131984366c79c95c29bb8225615eec69f579d71d70da8fc158e4297f8be9f66e`
matches the GitHub-provided digest. All231 original inner file checksums match.
The compact receipt retains90 selected files with public-copy normalization and
original/published hashes; install report descriptions are omitted while actual
versions/dependency constraints and artifact URLs/hashes remain.

Product/Python/guest/generated/release/go inputs and `tests/dbt_revalidation` are
byte-identical between these two sources. Later docs and optional1.8 evidence
are not relabelled as either run. Both hosts build fresh exact-source Go1.26.10
hosts and verify their actual clean VCS identity; Ubuntu is linux/amd64.
Both retain Connector/Python26.10.0 and original pinned dependencies.

The original nine project files remain identical to experiment ab38beb2, including
plain `SELECT DISTINCT customer` over an actual TEXT column. No CAST,
SQL_BIG_RESULT, model removal, continue-on-error or adapter patch is used in1.7.

Each cell passes debug, seed, run/repeat, build, snapshot twice, docs generation
and full-refresh. Counts/statuses are checked from dbt result artifacts. Six
application relations have equal sorted rows across routes/threads; snapshot
comparison intentionally excludes generated validity timestamps and IDs.
Deliberately duplicated order_id produces exactly one generic uniqueness test
failure (CLI1) and two passes; subsequent SELECT succeeds. This is **data-test**
coverage, not dbt1.8 built-in unit-test support.

All four Ubuntu schemas finish at0; both guest cells have0 SQL connections,
host reaped and session directory removed. Independent final native cleanup
reports schema count0; CI's Stop containers step succeeds. No cold-machine,
capacity/resource-model or comparative performance claim. The original local
receipt and CI receipt retain their actual Python patch versions and environments.

[Local assessment](dbt-revalidation-evidence/local-f37b2a7b/assessment.json),
[Ubuntu assessment](dbt-revalidation-evidence/ci-41089916368/assessment.json),
[Ubuntu result](dbt-revalidation-evidence/ci-41089916368/result.json),
[checksums](dbt-revalidation-evidence/ci-41089916368/SHA256SUMS.json).

## Disposition and boundaries

Issue19's bounded repair revalidation is complete. The original old-source hang
remains historical FAIL; it is not relabelled. The exact tested1.7 CLI workflow
works after the adopted Fd_dup/worker-notification repair. An EOL adapter/core
profile is not a promise about newer dbt, other adapters, arbitrary projects or
all wire commands. No wire trace/full capability census was captured.

The Human-authorized one-off experiment used the registered manual workflow path
only on the experiment branch. No release transaction, default-branch policy or
protection change occurred. The branch-only workflow override is now restored to
its original definition after execution; the original7a9a6f72 workflow remains
available by exact source for receipt reproduction. Do not merge exploratory
history; any later maintained profile should select the smallest reviewed change.

The optional1.8 investigation remains separate: an unmodified upstream PR188
fails native integer fixture CAST; a later test-only `mariadb__safe_cast` macro
passes one signed-integer native/local-guest positive/negative example on branch
`experiment/dbt-unit-cast`. Neither adopting that unmerged adapter nor broader
fixture-type testing is authorized by this1.7 completion.


Evidence imported from commit `3787e3dc85221e0a01997c3410198e41e014a1fc` without changing the executed sources or receipt bytes. The only completion-report import edit updates the local evidence link and adds this provenance note. [Immutable replay source and inputs](https://github.com/masahitojp/mariamem/tree/7a9a6f72dc83bc7d9f1526fa9704d32bbcefc126/tests/dbt_revalidation) remain on their original experimental source; no runner or workflow override is integrated by this documentation import.
