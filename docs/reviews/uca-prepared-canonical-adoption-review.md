# Prepared UCA tables — candidate adoption review

**Decision now: adopt the bounded prepared-table candidate
`cbd25f027e804bbd529a85208589ba2dd2899b86`. Recommendation: adopt it.**
The decisive reason is that every measured Fork/CPU/whole-fixture pair improves,
while the exact canonical guest now passes independent builds, identical
106-file Go regeneration and the fixed correctness/failure/cleanup gates on
both supported hosts. This recommendation is candidate adoption, not a main
merge, Qualification, version choice or publication approval.

The strongest objection is the trade: ASCII SQL median rose2.0% in the small
Mac cohort and the guest gains2.75MiB of initial data plus a maintained numeric
input. I still recommend adoption because whole-fixture time improves in all
five pairs, held-child RSS falls, the original fast readers are retained and
all actual resolved tables match their original producer. This is not proof
that the SQL movement is noise or that SQL speed is unchanged. If that small
SQL cost is unacceptable for the intended workload, the recommendation changes
to defer adoption; another open-ended investigation is not an implicit condition.

## Fixed reviewed objects and scope

- Candidate: `cbd25f027e804bbd529a85208589ba2dd2899b86`.
- Main base included: `47121e1be0b399ba4e2270ce3e25c411ade0e2eb`.
- Earlier preparation: d7fa5537; original experimental report:e33fc6ce.
- Actual CI: [41961766293](https://github.com/masahitojp/mariamem/actions/runs/41961766293),
  [verified receipt](uca-prepared-ci-41961766293/README.md).
- [Original canonical checkpoint/performance cohort](uca-prepared-canonical-candidate.md)
  keeps its original local source identities; this review does not rewrite it.

The receipt is proposed on a separate evidence branch so the tested PR112 head
stays fixed and bookkeeping does not restart two heavy C builds. Its own commit
is not the tested runtime source. No product or test behaviour changes here.

## Previously agreed finite conditions

| Condition | Finding and evidence |
|---|---|
| Maintained version-bound source input, pristine checks before patching | SATISFIED: scripts/prepare_guest.py:41; scripts/uca_prepared.py:18; input manifest source/archive/Unicode/header/table hashes; CI input controls |
| Exact selector and original reader/fallback | SATISFIED within fixed profile: canonical constructor patch selects only IDs2048/2304 and shared level identity; other construction remains original; native Czech/default corpus runs on both hosts |
| Verification separate from ordinary profiling | SATISFIED: package-local integration test cases normal_ambient_ignored/profiling_does_not_verify/six_resolved_tables/corrupt_table_rejected PASS on both hosts |
| Two independent source builds / no experiment bypass | SATISFIED: original guest.json has two identical linked/guest hash pairs, actual WASM member hash matches, contract generated-go-v1 and no experimental patch; source build job127029530332 |
| Canonical Go/worker binding | SATISFIED: both106-file inventories equal actual candidate Git bytes, not just each other; full19-body/TLS proof retained at original local checkpoint; six ownership controls including intentional unsafe failures PASS per host |
| Native SQL / subsequent independent children / Snapshot / disposal | SATISFIED: actual original semantic vectors match the fresh native control; both source-bound platform results have two children and zero refs/exit0/reaped/no root; Snapshot smoke is1 passed per host |
| One same-fixture performance comparison with CPU, RSS and SQL | SATISFIED, MAC ONLY: five alternating pairs at original40dd1e2a, linked from checkpoint; Fork -23.4%, CPU -15.5%, whole -5.3%, one-child RSS increment -5.0%, ASCII +2.0%; no Ubuntu/scaling speed claim |
| Preserve identities and cleanup | SATISFIED for the original task; new ZIP/member checksums recorded before disposing receipt staging; no old CI receipt points to a new source |

## Remaining items and detection net

1. **Protected integration checks are separate and currently missing at the PR
   head.** `gh pr checks112 --required` reports no required checks; the only new
   branch run is the four-job candidate workflow. The old Development run
   41943084029 belongs to d7fa5537. Before merging, run the normal `check`,
   `integration` and `Live required gate` on the actual integration head and
   meet strict-base protection. GitHub protection detects missing checks at merge;
   the candidate matrix does not cover that gate. This is not a new experiment.

2. **Adoption bookkeeping remains before main.** The tested source's canonical
   build/fixture status labels still describe authoring/CI-pending checkpoints.
   Update those current labels and source-bound CI pointers as part of approved
   integration, preserving incoming single-build origin275c1807 and the original
   raw CI sourceCBD. No runtime or expected hashes need change for that record.
   Existing test inventory checks do not detect the prose/status drift.

3. **Performance bounds stay explicit.** There is no CI detector for a2% SQL
   regression, no new Ubuntu performance result and no exclusive optimized Fork
   phase decomposition. The finite agreed comparison is complete; these are
   limits of the adoption decision, not missing general-purpose proof. Accepting
   this recommendation accepts the measured tradeoff, not a blanket speed claim.

## No additional gap found in the checked boundaries

No public Go/Python API or supported wire/profile expansion was introduced.
Canonical source owns the constructor; immutable inputs have one owner and no
runtime decoder. scripts/generated_release.py:85 rechecks prepared input
provenance, and both actual CI build guards executed successfully. No generic
ABI matcher, live-state clone, prewarm pool, InnoDB tuning or new resource campaign
is included. Exact unknown-body/guest/data guards remain fail-closed. Prior
main Go Pipe/host/wire work is retained by the pinned base.

Review method: original GitHub run/job/artifact metadata, downloaded ZIP digest
and member checks, independent receipt/Git inventory comparisons, fixed-source
code/conditions and the already-retained performance reduction. No C build,
guest run, timing campaign or CI rerun was performed for this review. Cold-host,
arbitrary Unicode tailoring/application support and later Release acceptance
are outside this recommendation.
