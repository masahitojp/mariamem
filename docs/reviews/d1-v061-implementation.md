# D1 product implementation checkpoint

The public-entry candidate is implemented and locally verified. Both supported
OSes and installed-wheel acceptance remain unverified; #43 stays open. Main
adoption and any versioned release are separate decisions. This checkpoint
records implementation, not a completed adoption review.

## Artifact and verification

Executed adapter source_commit: `8dddabb53ee2f886811fe64535eac2f2b7ff1ec9`.
Both campaign collectors recorded a clean checkout and hashes of the adapter,
harness, authored orders app/migrations and reused failing-migration inputs.
Later evidence/documentation commits do not replace this execution identity.

The local host was reused from the published v0.6.0 macOS arm64 wheel; no host
was rebuilt and no heavy CI was submitted. Host source_commit:
`b3b3b46a8807482ad3f96725af86e031fe369b01`; annotated v0.6.0 tag_object_sha:
`b57183b08d48884840111e8b53daa500734337f0`. Wheel SHA256:
`0c49fcd9f571851d8d37c6ec0fd089fad45609b281dc4fb0e8479819752e1519`;
host SHA256:
`b467baece270d6d3cb0770781695c1960de2c0d9c4bd536d6aac2c14f37c1e2a`.
The wheel hash and manifest host hash were checked; Go build metadata identifies
Go1.26.10, that source revision and `vcs.modified=false`.
These are Python-adapter tests on a reused host, not new candidate-host build
or installed-wheel qualification.

macOS27.2 arm64, Python3.11.18 and3.14.10, Django5.2.8,
pytest9.0.2, pytest-django4.12.0 and mysqlclient2.2.7 each passed all20 scenario
assessments (10 per runner): healthy, reverse, expected body failure after
commit, class setup failure, class skip, seed failure, genuinely retained SQL
connection, partial-DDL migration failure, two invocations in the same process,
and a database-free SimpleTestCase suite. Each observed host PID was gone after
normal finalization, without forced cleanup. Commit visibility uses a separate
physical connection; raw SQL/DDL state and class-data copies are checked.

Expected nonzero test exits remain nonzero and appear in raw stdout. A scenario
assessment PASS means its declared success/failure/skip, admission, preparation
counts and host retirement were observed. It does not rewrite failed tests as
successful. This is not an FD/schema census or proof of every possible guest I/O
failure. Disconnect/capture/fork/close fault controls also include deterministic
fake handles; these do not claim genuine engine-side fault injection.

Focused ownership, framework-policy, existing recipe/CI selection/reuse and
packaging/license checks: **84 passed on each Python minor**. Public source
checks and `git diff --check` also passed. No Go/guest/generated code changed.

Compact raw outputs, events, input hashes and assessments are under
[d1-v061-implementation-evidence](d1-v061-implementation-evidence).
`checksums.json` retains raw and saved hashes. Saved text normalizes the worktree
and home prefixes and trailing whitespace; no error classification is removed.
Earlier development attempts are not acceptance evidence: sandboxed TCP binding
was refused before settings loaded; an initial serial-option guard incorrectly
rejected Django's default `parallel=0`, and a skip-output assertion needed
pytest's `-rs`. Both were corrected before the pinned final execution.

## Resulting behavior and remaining conditions

[The candidate guide](../django-prepared.md) fixes the opt-in settings helper,
runner, cases and explicit pytest plugin. Existing Django TestCase is unchanged.
Class setup is materialized without a class-wide atomic, including immediate
on_commit behavior; test-local TestCase atomics remain. Unsupported modes are
rejected, and nested runner entry cannot close the active outer run.

Every acquired handle stays tracked until consumed or successfully closed;
retirement failures stop admission. Cleanup tries sibling owners and preserves
original and cleanup exceptions, including teardown errors Django ordinarily
suppresses after a run failure. Both runner test-environment state and database
settings are restored on failure. Completed invocations can start a fresh run.

The existing Release Django job now installs the already verified shared wheel
and runs this entry using that installed package, on both existing OS/Python
profiles. It also runs the focused component tests and keeps the existing
native authored-orders controls. It adds no workflow, host build, browser or
native reference campaign. Daily tests add lightweight ownership/policy checks;
they start no host for D1. No Release run was dispatched for this checkpoint.

Before closing #43:

- Obtain the two-OS/Python installed-wheel results from the existing Release
  path; retain the original failed outputs if a cell fails.
- Review the bounded candidate against #43, including class atomic semantics,
  failure evidence and unsupported options; obtain main adoption and integrate
  through normal protected checks.
- Synchronize #43 and the historical deferral's current disposition after those
  conditions are met. Publication of v0.6.1 remains separate.

No Oscar/arbitrary-project matrix, new engine/wire feature, resource-tuning
campaign or performance claim was added to this work.


## Human conditional shape approval — 2026-11-02

The Human approved this explicit opt-in shape, conditional on three items before
merge: (a) the existing Release Django installed-wheel job PASS on macOS15 arm64
and Ubuntu24.04 x86_64 with Python3.11/3.14, (b) release-note staging, and (c) one
paragraph defining exclusion from routing/shadow_maria. This is not permission
to merge before those conditions, publish a release or claim completed evidence.
The strongest objection is the second connection-switching entry plus its
nonstandard class transaction semantics. Explicit opt-in preserves the ordinary
entry; combining owners remains unsupported. If unified routing/prepared
ownership is requested, stop implementation and compare designs first.

The staging notes and exclusion paragraph are now present; the README/Python
entry lists distinguish the candidate from published0.6.0. Detailed resource
measurement remains deferred to0.7.x. The installed-wheel matrix remains pending
until the submitted Release verification actually succeeds.

### Failure evidence map

| Boundary | Actual local evidence | Controlled component evidence / limits |
| --- | --- | --- |
| Seed / partial migration failure | Both runners retain the real callback or MySQL error, admit no body and reap the host | Full engine I/O fault injection is not claimed |
| Disconnect / capture admission | A genuinely retained SQL connection prevents preparation; no body starts and the real host is reaped | This is the SDK wait-disconnected boundary, not a real `snapshot()` rejection after admission |
| Capture consume / preserve | Healthy real SDK capture consumes the source and independent Forks restore schema/seed | Rejected/failed capture ownership paths use fake handles, including failure after consumption; no real capture-I/O failure injected |
| Fork | Real baseline Forks cover class/test/teardown ownership and isolation | Fork-operation failure uses a fake handle; real startup/allocation failure was not injected |
| Close / admission debt | Normal finalization reaps all44 locally observed host PIDs; committed/assertion failures still restore the next test | Close failure, retry, sibling finalization and later-body refusal use fake handles; no genuine engine close-I/O failure injected |
| Primary plus cleanup error | Raw real test failures stay failures | Component/framework probes retain both exception objects, including teardown Django would suppress |
| Class setup / skip / repeat | Both real runners cover failure/skip, per-class data and repeated runs in one process | Not arbitrary user hook or project compatibility |

The existing common SDK capture precondition oracles in
[tests/snapshots.py](../../tests/snapshots.py) separately exercise real Busy and
transaction rejection with preserved source usability. They are unchanged common
runtime checks, not new D1 fault-injection evidence. No component oracle silently
substitutes for an unexecuted real fault. The final review should judge this
finite map against #43; “every possible engine I/O failure” is not a new gate.
