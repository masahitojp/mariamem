# Explicit Alembic preparation recipe

Status: adopted by the Human on 2026-10-24; recorded here during #158 cleanup.
Selected landing source_commit `ba379e1e204761013bc5153dcc5cb47151590323`, based
on `22c647d39c94d1e912699613c70d762732c01598`. This is not release approval.

Adopt the explicit configuration-reading Alembic migration/seed guide, its
Python/routing guide links and maintained `tests/preparation_migration_acceptance/`
checks. Users choose preparation explicitly; automatic preparation routing,
other migration frameworks, external legacy apps, dump import and Live Reset
retain their separate boundaries. No runtime/API/guest or product dependency
was added by this decision. The spike implementation was not adopted.

The maintained acceptance directory, classifier and workflow were byte-identical
to CI source_commit `94d51e6ea6a663aaabfee92d2103bae1c7fefbf4`.
[Run 40079827071](https://github.com/masahitojp/mariamem/actions/runs/40079827071)
covered macOS arm64 and Ubuntu x86_64 with Python3.11/pytest7 and
Python3.14/pytest9: serial/two-worker success and both exact preparation-failure
cases. This finite recipe acceptance is not general framework compatibility or
current-HEAD acceptance. Reconsider the boundary when a concrete migration
workflow needs capabilities beyond the explicit recipe.

The [original adoption record](https://github.com/masahitojp/mariamem/blob/a45604e848ff8f58c684f05016b994b7e6e6f7eb/docs/reviews/v06x-preparation-migration-main-adoption.md)
retains the original scope and identity context. Raw CI copies are no longer
required in the current source tree.
