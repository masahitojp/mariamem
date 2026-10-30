# dbt revalidation — local repair confirmed; Issue19 incomplete

2026-10-31 JST. **The original dbt TEXT DISTINCT failure is resolved on the
observed macOS27.2 arm64 host.** Native Ubuntu24.04 x86_64 remains NOT_RUN;
this does not close Issue19 or establish general dbt support. Recommend retaining
this local result and performing the same fixed replay on native Ubuntu before
judging the whole profile. The strongest limitation is that the native MariaDB
reference here is an amd64 container emulated on arm64, not Ubuntu-host evidence.

## Fixed source and inputs

- Base main source_commit: `cfc0421dc9b886ea4bf56d5c46083b374c9a2e2d`.
- Executed source_commit: `f37b2a7b86b7187613edc99c6aac069eef5071ac`.
  The delta only adds the plan, replay tool, dependency pins and original project;
  no product/guest/generated/API/release input is changed.
- Source identity was inspected with `scripts/git_identity.py`; the host's actual
  Go1.26.10 build stamp is this commit with `vcs.modified=false`. The runner
  rejects a dirty checkout, mismatched HEAD, toolchain or embedded source.
- All nine project files are byte-identical to original experiment commit
  `ab38beb282f3609a5ddb5849f81085aff34f2133`; original runtime receipt cc00ccd is
  historical. File hashes and original/published evidence hashes are saved.
- CPython3.11.18/OpenSSL3.5.9, dbt-core1.7.20/dbt-mysql1.7.0/
  Connector/Python26.10.0. All original runtime dependency pins were restored;
  pip/setuptools and the old inspection-only PyMySQL are not workload dependencies.
  The resolved environment is saved separately. This is an EOL core profile,
  not a result for current arbitrary dbt or Python3.14/OpenSSL4.
- Native image digest is
  `mariadb@sha256:2f4f46f80e7251990bfdc601ae3f7f2964ddb4dc1868f7deca699fc1ece8c35e`;
  image ID and architecture are retained. Both servers report12.3.3.

## Observed result

| Route | threads | Nine normal commands | Generic failure oracle | Final cleanup |
| --- | --- | --- | --- | --- |
| native container |1| PASS | expected uniqueness FAIL, subsequent SELECT PASS | schema count0 |
| guest macOS arm64 |1| PASS | expected uniqueness FAIL, subsequent SELECT PASS | schema/connections0, host reaped, directory removed |
| native container |4| PASS | expected uniqueness FAIL, subsequent SELECT PASS | schema count0 |
| guest macOS arm64 |4| PASS | expected uniqueness FAIL, subsequent SELECT PASS | schema/connections0, host reaped, directory removed |
| guest native Ubuntu x86_64 |1/4| NOT_RUN | NOT_RUN | NOT_RUN |

Normal commands: debug, seed, run, repeat run, build, snapshot twice, docs generate
and full-refresh run. Model run has4 successes, build10, snapshot1 each; result
JSON status/counts are checked, not only CLI exit0. The original customer column
remains TEXT and the model uses plain DISTINCT: no CAST, SQL_BIG_RESULT, model
removal or continuation on unexpected error. Deliberately duplicating order_id
makes exactly one of three selected generic tests fail with CLI exit1.

Six application relations have identical sorted rows across all four observed
cells. Snapshot comparison includes business columns and the expected3 rows;
generated validity timestamps and snapshot IDs are explicitly excluded. Catalog
nodes are checked, but this is not an exact metadata/capability census or proof
of unsupported wire commands. No wire trace was captured. Actual application
success must not be labelled coverage of COM_RESET_CONNECTION or other commands.

Sum of the nine normal CLI wall times: native threads1 18.118s / threads4 14.426s;
guest threads1 13.928s / threads4 13.774s. These are one warm local observation,
exclude installation/build/expected-failure time, use emulated reference SQL and
are **not a comparative performance or cold setup-cost claim**. No peak-resource
campaign was run. The dedicated native container and anonymous volume were removed.

[Assessment](dbt-revalidation-evidence/local-f37b2a7b/assessment.json),
[raw-result public copy](dbt-revalidation-evidence/local-f37b2a7b/result.json),
[input hashes](dbt-revalidation-evidence/local-f37b2a7b/inputs.json),
[checksums](dbt-revalidation-evidence/local-f37b2a7b/SHA256SUMS.json).
Public copies normalize workspace prefixes; original/published hashes are retained.

## Reproduction and remaining decision

Use `tests/dbt_revalidation/requirements-py311.txt` in a dedicated Python3.11 venv.
Use a clean independent clone when a nested worktree makes Go scan the ancestor
checkout. Build `./cmd/mariamem-host` with Go1.26.10, CGO_ENABLED=0, `-p1 -trimpath`.
The runner verifies the actual embedded identity before connecting.

Start an **exclusive disposable** native container from the exact digest above,
empty root password, port bound only to127.0.0.1. The runner drops/recreates the
`test` schema, so an existing application endpoint must never be supplied. Run:

```sh
python tests/dbt_revalidation/run.py --source-commit <exact-clean-source-commit> \
  --host-binary <matching-host> --native-port <exclusive-reference-port> \
  --output <fresh-evidence-directory>
```

Bound execution with `scripts/experiment_disk.py` (absolute work-dir,16GiB free
reserve,8GiB owned budget,1800s timeout). Remove the owned container and anonymous
volume after success or failure. Preserve result JSON/logs before cleanup.

The first launcher used an incorrect relative executable path and never ran dbt.
Its automatic failure cleanup deleted recreatable venv/build output; these were
restored. A later source preflight correctly rejected an ancestor-checkout stamp
(4cf4393d, dirty); no SQL was executed under that rejected identity. The accepted
run used the clean independent clone. These are tooling/preflight failures, not
additional dbt results. They count against the initial2-hour active budget;
roughly20 minutes active including tooling/diagnosis (estimate),0 heavy CI runs.

Issue19 still requires native Ubuntu replay. Current Human-approved CI policy
places heavy feature acceptance in Release CI only. No new standalone heavy
workflow or release transaction was started. Next execution needs either placement
in the existing Release acceptance with its normal submission decision, or an
explicit one-off CI policy exception for this fixed replay. The same runner and
pins are ready; no additional measurement infrastructure is a prerequisite.
