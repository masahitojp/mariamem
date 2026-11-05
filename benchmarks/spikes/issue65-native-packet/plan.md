# Issue65 native packet entry — bounded follow-up

Human authorization: 2026-11-05, continue Issue65 after clarifying that the goal
is to reduce host-side MySQL wire maintenance by reusing MariaDB's own protocol
implementation. Socket publication alone is not the success criterion.

## Decision and hypothesis

Can the existing MariaDB12.3.3 embedded SQL/storage path be combined with native
server protocol/session code behind one byte-stream entry, without recreating
handshake, statement parsing, result framing and statement lifecycle in an adapter?
Use the result to recommend continue / reject / inconclusive, not main adoption.

## Fixed inputs and environment

- Main baseline source_commit: `47121e1be0b399ba4e2270ce3e25c411ade0e2eb`.
- MariaDB source_commit: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` (12.3.3),
  checksum-bound by the product release input lock.
- Experiment branch: `experiment/issue65-native-packet`.
- Native Linux/arm64 build/run in the existing checksum/identity-recorded Docker
  build image on the current macOS arm64 host; do not call this WASIX acceptance.
- Original checkout's four user modifications remain untouched.

## Finite evidence and exit

Inspect compile guards and symbol dependencies; attempt the smallest justified
native build/prototype. Exercise one real-driver connection: handshake, SELECT1,
prepared parameter execution, following query and QUIT/disconnect. Record who
handles packets (native MariaDB versus handwritten bridge), state/lifetime owners,
source patches, exact build/runtime identities, failures and unverified boundaries.
A native ordinary-server/socket control alone cannot count as an embedded packet
entry. No experiment results may replace current product runtime acceptance.

## Budget and inconclusive exit

Initial active-work ceiling2 hours, including at most30 minutes of measurement
instrumentation; heavy CI0. Initial disposable disk budget6 GiB with8 GiB minimum
free space, owned timeout below2 hours, native build parallelism bounded after
checking other active work. Expected source/configuration/minimal target build is
roughly15–40 minutes elapsed if native dependencies permit; this is an estimate,
not a success promise. Do not silently build a full WASIX guest or full matrix.
Stop at a finite source/compile/runtime obstacle if this boundary cannot be proved
within budget; report missing evidence, concrete next work/cost and alternatives.
Preserve compact source/patches/logs/hashes, commit useful evidence, and remove
owned source/build/cache/container state. Existing services/caches are not ours.
