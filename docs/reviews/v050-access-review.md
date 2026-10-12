# v0.5.0 access-path assessment and investigation exit criteria

**Follow-up:** the approved bounded R1–R5 work is reported in the
[semantic investigation](v050-semantic-audit.md). It supplies per-target and
supporting-route dispositions, two reproduced helper boundary defects and one
specifically investigated unresolved join/publication edge. Coverage completion
is separate from fix completion and release judgment. The five-hour cap was not
used as an acceptance criterion; hourly reports were cancelled by the Human.

The review below records the earlier incomplete assessment and the contract
which governed that follow-up. The prior recommendation to proceed directly to
Qualification/Product Validation remains superseded by the follow-up's concrete
T1/T2 fix recommendation and the
[current bounded J1 decision task](v050-human-review.md).

The strongest concern with further investigation is an unfinishable demand to
prove that no failure can occur in any execution. That must not be the exit
criterion. Conversely, identifying a few important paths and listing everything
else as generically unproved does not fulfill the requested investigation.
The contract below separates coverage, correctness conclusions and unresolved
engineering questions. It does not withdraw the approved exact-width fixes.

The [concrete worklist](#concrete-worklist-and-cost-boundary) below is the current
execution boundary. It replaces the unsupported conversational 6–10 hour
completion estimate with explicit questions and a capped investigation budget.

## Review basis and findings

Reviewed source commit: `b779ce77216d5f4f5d4441cedfa626d826e2c725`, checked as a
commit object using `scripts/git_identity.py inspect HEAD`. Runtime remains
`f66727dda49d1b4ca2c7e814e218587c051f7f97`. This review reads the saved reports,
scanner, probe, inventories and receipts; it does not rerun or independently
re-prove the earlier runtime corrections. All 36 files in the access-path
evidence's saved hash inventory match.

1. **High: the progression recommendation exceeds the completed scope.**
   The [previous opening](v050-access-paths.md) recommends progression while its
   coverage section explicitly limits lifecycle tracing to selected groups.
   The Human requested the overall path investigation before that decision.
   A caveat later in the report does not repair this mismatch. Treat that report
   as intermediate evidence and withdraw the progression recommendation.
2. **High: complete writer inventory is not complete access-path coverage.**
   The [scanner](../../benchmarks/spikes/v050-access-paths/scan.py) validates all
   65 functions / 147 writer sites, but every saved inventory row has the same
   `Source/lifetime review required` verdict. The narrative adds useful detail
   for selected groups; the inventory has no per-target lifecycle/dependency
   closure status. A reader cannot determine how much remains from the counts.
3. **High: searching known field names does not enumerate all access routes.**
   The 716 saved references come from selected MariaDB directories and named
   queries. WASIX archive identity is verified, but this reference loop does
   not scan WASIX semantic accesses. The direct-call graph records 24,025 lines
   containing indirect calls without resolving their targets; 17 of the 65
   writer functions themselves contain such calls. These counts do not imply
   24,025 relevant hazards. Relevant callbacks, raw aliases and object-wide
   accesses need targeted disposition instead of a generic exclusion paragraph.
4. **High: mutex is the clearest concrete conflict, not an exclusive diagnosis.**
   The [probe](../../benchmarks/spikes/v050-access-paths/mutex_probe.py) tests
   copied guest functions with a NORMAL mutex, partial TLS and four agents.
   Its final 2,000 protected updates and heap race reports are real evidence
   within that fixture. They do not establish coverage of condition variables,
   other lock types, wait/cancel/join protocols or all protected payloads.
   Rechecking at the host futex layer alone does not establish every guest-side
   predicate or publication guarantee. No SQL harm was demonstrated by this
   probe, and it is not a full SQL execution.
5. **Medium: dynamic evidence remains narrower than the static inventory.**
   The earlier observed guest scenarios reached 24 of 65 writer functions with
   AHI enabled. The later integration repeated functional scenarios but did not
   replace that with all-path observation. The other 41 functions have static
   classification, not new execution evidence. Ubuntu CI qualifies the prior
   focused narrow implementation checks, not the new mutex probe. These are
   coverage gaps, not findings of 41 defects or failed Ubuntu behavior.

The retained conclusions are the exact-width correction and its recorded
bounded checks, the identified source lifecycle protocols, and the concrete
mixed-access diagnostic. Neither “only mutex remains” nor “the product is
unsuitable for development” follows from these findings. Uncertainty is not a
measured probability of harm. Public user restrictions need concrete usage
consequences; these investigation details belong in development evidence.

## A finite investigation contract

“Overall” must describe the access routes relevant to the requested issue:
the fixed guest's narrow atomic targets, overlapping ordinary accesses, and
the synchronization/ownership/lifetime paths on which their conclusions depend.
It includes every inventoried family, not just the high-count SQL examples.
It must also establish the overall shared-access and synchronization structure
so that an omitted supporting primitive is visible. It is not a new request to
prove the absence of every unrelated defect in MariaDB or run a full race census.

Use the fixed guest/runtime identity, supported product operations and existing
configuration policy. Record the default configuration and each relevant
optional configuration separately. Do not silently exclude a difficult path
or redefine a supported configuration to close the investigation. macOS is the
current executable scope; Ubuntu and minimum-OS gaps remain explicit and cannot
be counted as native PASS from other fixtures.

Create a finite ledger before further experiments. Each of the 147 writer sites
must map to a target/protocol entry; multiple sites may share an entry with
evidence. Add dependencies discovered through ordinary readers, bulk operations,
host access and synchronization. Entries must state:

- source field/object and generated access, requested/effective width, and
  confidence of the field/offset binding;
- creation, publication, concurrent use, reuse, shutdown/drain and destruction;
- named readers/writers plus possible raw, wider, bulk/SIMD and host access to
  the same object; related indirect callbacks and their registration/targets;
- the synchronization or ownership invariant required, how the generated
  implementation supplies it, and any remaining assumption;
- observed scenario/platform, a targeted check if needed, concrete evidence,
  user consequence if the invariant fails, and disposition.

Do not enumerate all execution schedules. Group routes by a shared invariant
and verify that each grouped route actually uses that invariant. Reuse existing
receipts when they answer the question; add experiments only for a named gap.

Every entry ends in one of these states:

| State | Required evidence and meaning |
| --- | --- |
| Supported for the stated scope | Access/lifetime argument and relevant implementation/test evidence, with explicit assumptions; not a universal theorem |
| Excluded for the stated scope | Build/configuration, ownership or phase evidence that excludes the alleged conflict; an unobserved trace is insufficient |
| Confirmed violation | Concrete violated requirement and reproduction or implementation argument; separately state whether user harm was reproduced |
| Investigated, unresolved | Exact path and missing guarantee, methods attempted and their limits, remaining alternatives, and the specific additional work or decision needed |
| Not yet investigated | Missing analysis; this state prevents a claim that the overall investigation is complete |

“Investigated, unresolved” cannot be assigned merely because the work is large
or a generic alias proof is absent. It needs a concrete question and evidence
of the attempted analysis. Likewise, a generic “there could be an unknown raw
pointer” is not a confirmed risk: identify an actual escape route or explain
the abstraction/tool limitation preventing its exclusion for that object.

## Ordering the remaining work

1. **Coverage and structure first.** Reconcile every family and writer site with
   the ledger. Inventory ordinary/atomic/bulk/host access mechanisms and the
   guest's supporting synchronization classes. Resolve relevant indirect routes
   from table/registration evidence, or attach a concrete unresolved target set.
2. **Close lifecycle and dependency arguments.** Finish recovery, file/extension,
   encryption, buffer/I/O/resize, deadlock, checkpoint, startup/error teardown
   and other less detailed families. Revisit the important groups where their
   exclusions depend on an unverified mutex, CV, join or publication property.
   Mutex/futex analysis proceeds as a shared dependency, not the sole work item.
3. **Test named remaining questions.** Choose checks for mutual exclusion,
   publication, wait/wake, timeout/cancellation, completion/join and object reuse
   only where those requirements occur in the ledger. Tie relevant checks to
   actual guest scenarios; keep isolated fixtures distinctly labelled. Record
   heap/mmap/assembly observability and observer/control differences separately.
   A failed schedule or requirement is informative; repeatedly passing a stress
   test until confidence feels sufficient is not a completion rule.
4. **Return a coverage and consequence review.** Show confirmed violations,
   supported exclusions, specifically unresolved guarantees and platform gaps.
   Separate investigation completion from fix completion and release judgment.

The investigation is complete when every in-scope entry and dependency has a
substantiated disposition, no entry is merely unexamined, and the ledger can be
reconciled with the fixed-input inventory. Any unresolved entries remain visibly
unresolved; coverage completion must not be reported as correctness established.
If a concrete obstacle prevents even that analysis, stop with **investigation
incomplete**, naming the blocked entry and needed evidence. Do not relabel it
complete or ask the Human to accept the product risk to avoid doing the work.

This is a finite coverage-and-evidence goal, not an assurance that every question
will be resolved. A stronger guarantee can require a specific translation design
change, compiler/ISA argument or formal verification; report that need rather
than extending stress testing indefinitely. The Human chooses such additional
engineering after seeing concrete remaining questions. Existing authorization
to investigate does not need to be requested again.

## Concrete worklist and cost boundary

The engineering question is preservation of the relevant Wasm behavior by the
fixed translated runtime. A Go detector report is not itself a demonstration
of a Wasm-forbidden result. A successful SQL run is not a proof of preservation.
An allegation of a defect needs a requirement, an implementation location and
an actual semantic difference or a specific missing argument. No probability
of SQL failure has been measured.

The [Wasm threads overview](https://github.com/WebAssembly/threads/blob/main/proposals/threads/Overview.md#atomic-memory-accesses)
specifies sequentially consistent atomic operations and separately describes
wait/notify; thread creation/join belongs to the embedder. The
[Go memory model](https://go.dev/ref/mem) specifies synchronization and constrains
the behavior of racy reads; detecting a Go race does not identify which original
Wasm property, if any, was violated. The work must distinguish Wasm instruction
semantics from the pinned WASIX import ABI and product lifetime contract.
Before judging a disputed case, record the precise applicable specification
clause/version; these live links are orientation, not a frozen conformance suite.

Already established work is retained: bounded allocation/bulk/load corrections,
native narrow writer operand widths and value/boundary oracles, formal independent
regeneration, saved SQL/consumer checks and the existing native platform receipts.
There is no reason in this review to repeat all of those. Existing store-buffering,
IRIW, publication and mixed-width tests in the
[writer study](v050-exact-writers-design.md) already passed their bounded patterns;
R2 must identify a missing argument, not merely demand more of the same tests.

### R1 — Does ordinary/atomic mixing change allowed reads or synchronization?

- **Evidence:** [generated statements](v050-access-paths-evidence/generated-excerpts.txt)
  and [mutex fixture receipt](v050-access-paths-evidence/mutex-results.json).
- **Concrete basis:** Fn93 mutex lock, Fn130 unlock and Fn88 futex adapter use
  ordinary word reads alongside atomic updates. The copied NORMAL-mutex fixture
  reports heap conflicts while its 2,000 protected updates finish correctly.
- **Requirement:** generated reads and updates must preserve the applicable
  Wasm permitted-value/order rules; a preliminary read used by a retry loop must
  not be mistaken for the operation which acquires a lock or publishes data.
- **Question:** which ordinary reads influence correctness directly, and which
  are checked again by CAS or the host wait? Does Go compilation preserve the
  needed access/order property at those specific sites?
- **Method/output:** a statement-level table for these three functions identifying
  each read's consumer, revalidation, required property and implementation
  argument. Use an isolated check only for a named unresolved property. A
  counterexample must identify a Wasm-forbidden outcome, not just a race warning.
- **Stop:** record supported mapping, a concrete violation, or the exact compiler/
  mapping guarantee that cannot be established and the change needed to supply
  it. Do not keep repeating the 2,000-update fixture to seek reassurance.
- **Allocated investigation time:** 60 minutes.

### R2 — Do native narrow atomics and Go atomics compose with the required order?

- **Evidence:** [native primitive owners](../../scripts/runtime_correctness/narrow_write_darwin_arm64.s.txt)
  and [existing ordering results](v050-exact-writers-design.md#verification-and-actual-identities).
- **Concrete basis:** 8/16-bit accesses use native assembly while full-width
  operations use Go atomic primitives. On arm64, the narrow helpers contain
  DMB and acquire/release instructions. Existing ordering/value tests passed.
- **Requirement:** the combined execution must respect the Wasm atomic ordering
  and required publication of surrounding data, not just use the right width.
- **Question:** is the argument complete across the Go call/compiler boundary,
  the selected ISA instructions and the surrounding ordinary payload accesses?
- **Method/output:** reuse saved disassembly and existing tests; document the
  composition argument and any exact missing compiler/ISA premise. Only a new
  untested pattern warrants another small fixture. Do not re-audit the already
  established operand-width correction without contradictory evidence.
- **Stop:** one mapping argument or a specifically unsupported premise with an
  implementation remedy. A missing race-detector annotation is recorded as an
  observation limit, not automatically as a product semantic defect.
- **Allocated investigation time:** 45 minutes.

### R3 — Do the actual wait/notify protocols preserve their contract?

- **Evidence:** [AtomicWait and wake implementation](../../internal/generatedgo/code/base/base.go),
  [host import mapping](../../internal/generatedgo/main.go) and
  [function graph](v050-access-paths-evidence/direct-call-graph.json).
- **Concrete basis:** `AtomicWait` compares/registers under `parkMu`; wake uses
  the same lock. WASIX `Futex_wait` converts timeout/result values and writes a
  result byte. The earlier check covered a NORMAL mutex, not the full CV route.
  The graph identifies Fn218/226 condition waits, Fn220 signal and Fn4052
  broadcast, besides Fn88/89 and the mutex functions. It also identifies rwlock
  Fn209–213; disposition of their use belongs here/R5, not a presumed new defect.
- **Requirement:** distinguish the imported WASIX futex ABI from direct Wasm
  wait/notify. Preserve compare/register/wake behavior and the applicable timeout
  and return-value rules. Retrying a source-level predicate is part of its protocol.
- **Question:** do guest-side checks, host wait registration, wake, timeout and
  return conversion leave a concrete route to a missed notification or incorrect
  result? Identify which cancellation/error cases this guest actually invokes.
- **Method/output:** one transition table and a caller/ABI map. Reuse existing
  wait tests and add deterministic schedule checks only for missing transitions.
  Do not assume every generic helper branch is used by this fixed shared guest.
- **Stop:** disposition of each applicable transition; any missing transition
  analysis is explicitly unfinished. Never infer fairness or a latency bound
  from finite runs; those are not the property under review.
- **Allocated investigation time:** 45 minutes.

### R4 — Is memory shared and retired at the correct lifecycle boundaries?

- **Evidence:** [AtomicsContended, ThreadLaunch and WaitThreads](../../internal/generatedgo/code/base/base.go)
  and [earlier lifetime review](v050-access-paths.md#important-target-paths).
- **Concrete basis:** full-width atomic helpers can use ordinary accesses before
  `AtomicsContended` becomes true. `ThreadLaunch` changes `nextTID` before the Go
  child starts. `WaitThreads` waits for workers. Guest join is separately Fn221;
  start/exit and host access are not proved by the counter alone.
- **Requirement:** the ordinary fast path must have no concurrent peer; completed
  initialization must be visible before use, and backing/object retirement must
  follow the applicable completion protocol.
- **Question:** can another guest agent or host callback access relevant memory
  before the transition, or after the asserted drain? Does each reviewed lifetime
  argument use the real completion event rather than a timestamp?
- **Method/output:** enumerate actual launch/host entry and completion routes;
  reuse prior startup/cleanup evidence. Trace only callbacks which can reach the
  relevant memory. Include object reuse/drain dependencies from R5 in this map.
- **Stop:** supported lifecycle edges or named missing edges with a specific
  consequence; generic distrust of all allocation/lifetime code is not an item.
- **Allocated investigation time:** 30 minutes.

### R5 — Have all relevant guest target families been accounted for?

- **Evidence:** [complete writer inventory](v050-access-paths-evidence/writer-inventory.json)
  and [selected source references](v050-access-paths-evidence/source-references.json).
- **Concrete basis:** the complete 65-function/147-site inventory has 14 primary
  families. Important target narratives exist; several remaining families have
  declarations and references but lack completed ownership/lifetime arguments.
- **Requirement:** the investigation's claims must apply to every inventoried
  target, including ordinary/bulk/host overlaps and supporting synchronization,
  rather than just paths reached by the earlier SQL scenarios.
- **Question:** does each target use a protocol already covered by R1–R4, an
  independent supported protocol, or a concrete additional access mechanism?
- **Method/output:** reconcile all sites into one ledger using the existing
  inventory, 716 source references and graph. Cover guard, pool, view, purge,
  encryption, file, recovery, load, startup/shutdown, deadlock, AHI, buffer/I/O,
  checkpoint and table-cache families. Trace relevant callback registrations and
  whole-object/raw accesses; do not resolve all 24,025 indirect-call lines merely
  because they exist. An unresolved relevant callback gets a concrete target set
  and object relationship. Unobserved functions are not called unreachable.
- **Stop:** every site maps to a substantiated disposition and dependencies. If
  that cannot be achieved within the allocation, enumerate the exact unfinished
  targets. Do not label the overall investigation complete in that case.
- **Allocated investigation time:** 90 minutes.

These are five work packages, not five established defects. Possible user
consequences depend on a demonstrated violation: R1/R2 concern observed values
and publication, R3 concerns waits/results, R4 concerns lifecycle access. R5 is
a coverage obligation and creates no additional failure claim by itself.

### Cost and stopping discipline

The first investigation allocation is **300 minutes maximum**: R1 60, R2 45,
R3 45, R4 30, R5 90 and final evidence/report 30. This is a budget to produce
dispositions, not a promise to resolve every guarantee or complete every target
within five hours. The previous conversational 6–10 hour completion estimate
was not supported by a task-level estimate and is withdrawn. Do not replace it
with an equally unjustified claim of guaranteed five-hour completion.

Begin by laying out R5's target ledger, then answer the shared R1–R4 dependencies
once and reuse those answers in it. Report a checkpoint after the first hour:
closed questions, exact open questions and allocation consumed. At each package's
allocation, record its disposition or concrete unfinished work. At 300 minutes,
stop and report, even if an item remains unfinished. No unannounced extension
or new stress campaign is included. Actual compiler/build time counts against
the allocation; do not discard failed setup time to appear within budget.

The report must distinguish: supported mapping; confirmed semantic violation;
investigated but specifically unresolved; and not yet investigated. Only the
last category prevents coverage-complete status, while any unresolved guarantee
still prevents claiming that guarantee. A new issue may enter the list only
with its requirement, exact code/path, evidence and decisive check; otherwise
it is not a release blocker. A concrete defect found during the work is reported
immediately. Its fix is separately scoped instead of silently lengthening this
investigation. This cap is an explicit cost boundary, not a claim that safety
follows from time spent.

Current scope is macOS execution and existing native Ubuntu receipts. New Ubuntu
experiments, guest-wide race census, final Qualification, Product Validation,
runtime changes and publication are not hidden inside this allocation. Platform
gaps stay labelled, without weakening or re-running unrelated existing checks.
This document is the requested pre-experiment worklist; no R1–R5 completion is
claimed by having written it.

## Status of this review

The Human requested exit-criterion clarification before further investigation.
This document supplies that clarification and the review findings. No new guest
experiment, runtime implementation, Qualification or Product Validation occurred.
Documentation wording, references, saved evidence hashes and diff are checked;
unchanged runtime tests are not repeated. The original overall investigation
remains incomplete. Development records preserve the uncertainty without turning
it into an unsupported public warning or a release recommendation.
