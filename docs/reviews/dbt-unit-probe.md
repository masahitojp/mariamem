# dbt1.8 model unit-test probe — blocked on native adapter SQL

2026-10-31 JST. **An unmerged dbt-mysql1.8 port exists, but its unmodified
model unit test fails on native MariaDB12.3.3 before mariamem is involved.**
Recommend stopping this light probe here: preserve the positive dbt1.7 repair
replay separately, and treat newer model unit tests as adapter work requiring a
separate decision. The objection is that this is one tiny case, not proof that
all model unit-test formats fail. SQL fixtures or a narrow adapter macro change
may bypass this exact cast error; neither was tested or adopted here.

## Sources and finite scope

[Upstream PR188](https://github.com/dbeatty10/dbt-mysql/pull/188), observed open
and unmerged, head source_commit `d4186f78984aa891f73d3f256f5780630878b21f`.
The [pinned setup.py](https://github.com/aabeds/dbt-mysql/blob/d4186f78984aa891f73d3f256f5780630878b21f/setup.py)
adds dbt-adapters/common dependencies and targets dbt1.8. The PR's Python
`tests/unit` changes concern adapter initialization, not evidence of dbt model
unit-test success. Published dbt-mysql1.7.0 remains distinct.

Source identity was inspected with `scripts/git_identity.py` before installation.
No source/dependency override or local adapter patch was used. Normal pip
resolution succeeded with dbt-core1.8.7, dbt-mysql1.8.0a1, dbt-adapters1.8.0,
dbt-common1.12.0 and Connector/Python26.10.0 under Python3.11.18. Resolved
packages and pip's source/artifact report are saved. This was a scratch local
probe, not a mariamem runtime build or qualification.

Question/exit was fixed before execution: try one small built-in model unit test
against the disposable native12.3.3 reference; stop on the first prerequisite
blocker, otherwise try a wrong-expected result and guest only if time remains.
Budget <=30 minutes active including <=10 minutes scratch tooling, zero heavy
CI. Actual active time approximately10 minutes including investigation and
preservation (estimate); no performance/resource measurement infrastructure.

## Minimal case and observed failure

Upstream model `orders` returns one row with integer order_id/amount. Model
`doubled` is:

```sql
select order_id, amount * 2 as doubled from {{ ref('orders') }}
```

Unit fixture provides `(1,10), (2,7)` and expects `(1,20), (2,14)`. Native
`dbt debug` succeeds and `dbt run --select orders` succeeds. Then:

```sh
dbt test --select test_type:unit
```

Both `type: mysql` and `type: mariadb` discover exactly one unit test and return
CLI exit1 / result status `error`, errno1064 / SQLSTATE42000. Fixture SQL contains
`cast(1 as int(1))` and `cast(10 as int(2))`. Native MariaDB rejects that cast type
syntax. Thus installation and ordinary model execution work, but the model unit
test does not yet work unmodified. The evidence supports an adapter-generated
SQL compatibility blocker; it does not establish a mariamem wire defect.

[Compiled SQL](dbt-unit-probe-evidence/compiled-mariadb.sql),
[mysql log](dbt-unit-probe-evidence/unit.txt),
[mariadb log](dbt-unit-probe-evidence/unit-mariadb.txt),
[assessment](dbt-unit-probe-evidence/assessment.json),
[checksums](dbt-unit-probe-evidence/SHA256SUMS.json).

Reference image is the same fixed12.3.3 digest as the1.7 replay. It executes
amd64 emulated on the observed macOS arm64 host; this is not native Ubuntu
acceptance. Final schema_count_after=0. Guest and wrong-expectation control are
NOT_RUN because the native prerequisite failed. No broad1.8 compatibility,
unit-test support, Issue19 completion or new release prerequisite is claimed.

## Next option, separately scoped

A second small spike could investigate adapter `safe_cast`/fixture type mapping
for MySQL/MariaDB CAST syntax, then rerun this exact positive/negative test on
native before guest. Allow at most30–60 minutes initially; successful integer
casts would not establish string/decimal/date/NULL fixture correctness. Owning or
maintaining an adapter fork, submitting an upstream change and adding product
acceptance remain separate decisions. This probe did none of them.

Original Issue19 still asks whether its fixed dbt1.7 workload is repaired on
both supported hosts; its macOS PASS and outstanding native Ubuntu replay are
unchanged by this optional1.8 investigation.
