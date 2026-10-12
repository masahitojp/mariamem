# v0.5.0 access-path assessment and investigation exit criteria

**Current assessment: the requested access-path investigation is incomplete.**
The previous recommendation to proceed to Qualification/Product Validation is
withdrawn. The next step is to establish a finite investigation contract before
additional experiments. This is an engineering review, not a request to accept
an unspecified product risk or a decision about publication.

The strongest concern with further investigation is an unfinishable demand to
prove that no failure can occur in any execution. That must not be the exit
criterion. Conversely, identifying a few important paths and listing everything
else as generically unproved does not fulfill the requested investigation.
The contract below separates coverage, correctness conclusions and unresolved
engineering questions. It does not withdraw the approved exact-width fixes.

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

## Status of this review

The Human requested exit-criterion clarification before further investigation.
This document supplies that clarification and the review findings. No new guest
experiment, runtime implementation, Qualification or Product Validation occurred.
Documentation wording, references, saved evidence hashes and diff are checked;
unchanged runtime tests are not repeated. The original overall investigation
remains incomplete. Development records preserve the uncertainty without turning
it into an unsupported public warning or a release recommendation.
