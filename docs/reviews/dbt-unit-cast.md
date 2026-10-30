# dbt1.8 integer fixture CAST spike — bounded native/guest success

2026-10-31 JST. **The same two-row dbt1.8 model unit test can run on native
MariaDB12.3.3 and the local macOS arm64 guest with a small project-local macro.**
Recommend retaining this as a bounded feasibility result. The decisive evidence
is paired before/after and wrong-expectation control on both engines. The main
objection is that signed integer fixtures are a tiny part of model unit-test
compatibility: unmerged adapter dependencies and other types remain unqualified.
This does not authorize adapter ownership, product adoption or an added0.6 gate.

## Fixed experiment

Human authorized a small follow-up after the unmodified adapter probe. Exit and
<=30min active / <=10min scratch-tooling / zero-heavy-CI budget were recorded
before execution in the [spike recipe](../../benchmarks/spikes/dbt-unit-cast/README.md).
The probe stayed within those bounds; elapsed wall time is not a measured active
work total. No continuous resource collector or additional CI campaign was added.

Executed source_commit `16110eb306a371e80b08abb0d92ec5fc10c7cb67`, based on the
previous evidence head0da022a2. Branch `experiment/dbt-unit-cast` adds only the
experiment source/records and excludes the ongoing1.7 Ubuntu workflow override.
That CI stays bound to7a9a6f72; it was not polled or changed in this task.

The adapter remains exact unmerged PR188 source_commit
`d4186f78984aa891f73d3f256f5780630878b21f`. Its Python/source was not patched.
Dependencies were restored from the previous resolved1.8 probe: dbt-core1.8.7,
dbt-mysql1.8.0a1, dbt-adapters1.8.0, dbt-common1.12.0, Connector/Python26.10.0,
Python3.11.18. Actual versions are saved. Native is the same12.3.3 image digest
`sha256:2f4f46f80e7251990bfdc601ae3f7f2964ddb4dc1868f7deca699fc1ece8c35e`,
amd64 emulated on the macOS arm64 host. Guest host was freshly built from an
independent clean clone with Go1.26.10; actual VCS/source/toolchain/hash were
checked before guest execution and are preserved. No runtime/guest/generated
inputs were changed.

## Change and results

The experimental project overrides `mariadb__safe_cast`: integer type spellings
such as `int(1)`/`int(2)` become `CAST(value AS SIGNED)`. Other types keep their
original CAST expression. This is a **test-only signed-integer experiment**, not
a general replacement for the adapter's CAST implementation. Unsigned values,
integer range/overflow/coercion semantics and other fixture types are untested.

The model doubles amount for fixture rows `(1,10)` and `(2,7)`, expecting20/14.
Both routes first create the upstream model and execute without the override,
then add the same macro, then change expected14 to15.

| Condition | Native12.3.3 | macOS guest |
| --- | --- | --- |
| Original project without override | expected CLI1/status error,1064/42000 | same expected error |
| Signed-integer macro | CLI0, exactly1 unit status pass | CLI0, exactly1 unit status pass |
| Wrong expected doubled value15 | CLI1, exactly1 unit status fail | CLI1, exactly1 unit status fail |
| Subsequent SELECT | PASS | PASS |
| Final schema count |0|0|
| Final guest connections/host/temp | n/a |0/reaped/removed |

The wrong-expected control prints the actual14 versus expected15 row difference;
it does not turn a SQL execution error into success. Positive compiled SQL is
byte-identical across the two engines. Native reference container/anonymous
volume were removed after the run.

[Assessment](dbt-unit-cast-evidence/assessment.json),
[native result](dbt-unit-cast-evidence/native/result.json),
[guest result and host identity](dbt-unit-cast-evidence/guest/result.json),
[readable mismatch](dbt-unit-cast-evidence/guest/wrong-expectation.txt),
[macro source](../../benchmarks/spikes/dbt-unit-cast/project/macros/integer_cast.sql),
[checksums](dbt-unit-cast-evidence/SHA256SUMS.json).
Public copies normalize only the workspace prefix; original and published hashes
are retained. Original no-macro failures remain errors, not relabelled PASS.

## Boundary and next decision

Only `type: mariadb`, one integer model, one supported-host local observation.
No new `mysql`-profile run, native Ubuntu replay, string/decimal/date/NULL/nested
fixture coverage, incremental/ephemeral unit-test claim, packet trace, general
adapter compatibility or performance claim. The fixture framework reports a
successful expected result, not blanket wire sufficiency.

A project macro is therefore a feasible entry for this tiny case; it avoids
patching mariamem and avoids committing to maintenance of an adapter fork.
Before treating it as a user-facing recipe, choose whether the project intends
to support this unmerged adapter profile at all. If chosen, the next finite task
would define a small representative fixture-type set and compare native/guest
positive and wrong-expectation controls, with a separate budget and explicit
upstream ownership. This spike does not start that work.

Issue19's original fixed1.7 workload and ongoing Ubuntu replay remain separate.
No product/API/guest/generated/release change, main integration, Qualification
or publication was performed.
