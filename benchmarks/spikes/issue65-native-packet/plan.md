# Issue65 — proposal to reduce handwritten wire maintenance

## Current authorization

Human clarification,2026-11-05: prepare the proposal first; consider experiments
only after reviewing it. No native build, packet-entry implementation, WASIX
regeneration or runtime experiment is currently authorized by this plan.
The earlier preparation interpretation is superseded by this clarification.

The aim is to delegate MySQL protocol semantics to MariaDB itself, reducing
per-driver fixes to the Go implementation. Socket exposure and transport speed
are secondary; moving handwritten packet handling from Go to C is not success.

## Proposed direction

Recommend first evaluating a byte-stream entry that uses MariaDB's native protocol
reader/writer and session lifecycle, while retaining embedded SQL/storage execution
where feasible. A thin host adapter would own byte transport and resource lifetime;
MariaDB would own handshake interpretation, command decoding, statement IDs,
parameter decoding, result/error framing and protocol state.

The strongest concern is that EMBEDDED_LIBRARY excludes parts of those server
paths and substitutes embedded result structures. Restoring them could require
more invasive changes than keeping today's Go wire code. The design therefore
needs a small, separately approved feasibility experiment before product work.

## Options to compare

| Option | Expected value | Main concern |
| --- | --- | --- |
| Add native protocol entry to an embedded-derived build | Preserve current engine/storage investment; reuse protocol semantics | Compile guards, THD/session initialization and embedded/native result-path coexistence are unproved |
| Build the normal server core behind host-provided virtual I/O | Retain a broader native protocol/server path, analogous in intent to pgmem | Larger guest/build/runtime boundary, background services and initialization/cleanup costs |
| Keep the current host wire implementation | Lowest immediate migration cost | Continued command/driver-specific compatibility maintenance |

A socket-only relay on the current unchanged guest was already rejected by the
[initial source inspection](../../../docs/reviews/v06x-wire-relay-feasibility.md).
The detailed Issue65 source-inspection report is on its original experiment ref:
https://github.com/masahitojp/mariamem/blob/9c86d469de09a2426503b2578c3d743c2b29e574/docs/reviews/issue65-guest-wire-feasibility.md
This does not prove a modified embedded entry or alternate guest impossible.

## Design questions before experimentation

- Which native protocol reader/writer and session-init boundaries are reusable
  without importing the whole standalone-server lifecycle?
- Can protocol state be owned per connection while SQL state remains in the
  existing embedded engine? Identify what must change, not just exported symbols.
- Where would byte transport, deadlines, disconnect, cancellation, no-response
  commands, fatal failure and joined cleanup be owned?
- How would the existing16-session budget, Snapshot/Fork and Live quiescence map
  to that ownership? Existing tests do not prove an absent replacement path.
- What upstream patch surface, regeneration cost and ongoing maintenance would
  remain? Judge the reduction in handwritten protocol semantics explicitly.

## Possible experiment, not started or approved

If selected later, first try one native Linux/arm64 connection: handshake,
SELECT1, prepared parameter execution, following SQL and QUIT. Check that MariaDB
actually parses commands and constructs responses; an ordinary TCP-server control
or a new handwritten packet codec cannot satisfy the proposed exit.
Preserve exact sources, compile guards, patch set, result bytes/errors and ownership
observations. Report continue / reject / inconclusive with concrete next costs.
Only then consider WASIX/Go generation and both-platform product acceptance.

Proposed initial ceiling:2 hours active work, at most30 minutes of instrumentation,
heavy CI0; disposable disk6 GiB and minimum free8 GiB. Reassess build/time estimates
before starting. These are proposal bounds, not approval to execute.

Reference inputs for the proposal: main source_commit
`47121e1be0b399ba4e2270ce3e25c411ade0e2eb`, MariaDB12.3.3 source_commit
`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.

## Preparation stopped after clarification

Before the clarification, a task-owned worktree was created, pinned source archives
were verified/extracted and native tool availability in an existing Docker image
was inspected. No MariaDB native build, source patch, packet-entry implementation,
SQL execution, guest rebuild or CI submission occurred. The owned preparatory
script and extracted source are discarded; the proposal and compact preparation
record are retained. Original checkout user changes remain untouched.
