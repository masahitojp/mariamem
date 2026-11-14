# Normal Development gate43457263372 — source metadata repairs

The first normal gate failed its source suite because license evidence still
identified the previous guest. Retained-library auditing was rerun against the
new linked/Wasm hashes, proven Binaryen map, actual generated definitions and a
clean-source native host at1f2fef0b4ff3e5a92728e08a3446feccf8f769a7. All12 recorded
component families have positive retained-symbol evidence. Canonical notices and
component/distribution obligations are unchanged; the evidence digest and Python
license inventory mirror now agree.

A broader local Python run reported1984 passed,99 skipped and14 failures before
these repairs. The failures also exposed two unregistered workflows/automatic
push triggers, old current12.3 overlay preimages and stale active fixture wire
source pins. These are repaired without weakening the checks:

- workflows are manual/callable only, with reviewed source-check classification;
- the product workflow selects canonical or public integration explicitly; public
  integration uses installed canonical source and does not rebuild the C guest;
- current12.3 descriptor pins the actual resident/prepared output overlays and
  source origin d8f66d9a; historical13.0.2 inputs are untouched;
- a new current wire inventory records only Ready's private v2 change within the
  four-file fixture boundary. Old Issue94 evidence and contracts are retained;
- license/mirror six tests pass; the combined related source repair suite167
  tests passes; final resolver/context replay13 tests passes;
- three local socket-denial failures pass when rerun with ordinary socket access.
  The remaining skips retain their existing opt-in/environment conditions.

No runtime source, accepted behavior or generated provenance is changed by this
repair. The broad run is not rewritten into a fresh all-suite PASS: normal CI
must confirm the final candidate. Full public integration/consumers on both OSes
is submitted as the next acceptance stage; installed distribution and performance
remain separate recorded work. No main/release approval is implied.
