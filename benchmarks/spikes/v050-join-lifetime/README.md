# J1 post-repair actual-function fixture

Run `package.py --output "$PROBE"` from the source root, then separately in
`$PROBE/module` (Go1.26.8):

```sh
JOIN_PROTECTED=0 JOIN_BACKING=heap go test -count=1 -v ./probe
JOIN_PROTECTED=1 JOIN_BACKING=heap go test -count=1 -v ./probe
JOIN_PROTECTED=1 JOIN_BACKING=mmap go test -count=1 -v ./probe
JOIN_PROTECTED=1 JOIN_BACKING=heap go test -race -count=1 -v ./probe
JOIN_PROTECTED=1 JOIN_BACKING=mmap go test -race -count=1 -v ./probe
```

The unprotected baseline must FAIL `early-free` with replacement byte 165 → 1
and PASS both controls. The protected matrix must PASS all four cases, preserving
165 and invoking raw reclaim once. Baseline exit 1 is a reproduced defect, not
a passing correctness oracle. `JOIN_PROTECTED=0` omits the completion owner;
the generated pre-free hook then preserves its original nil-owner behavior.

The package copies the actual guest function closure and canonical base owners,
with provenance checks. Prototype mode applies the same owned installer adapter
to baseline copies; it is explicitly unqualified. Final receipts use canonical
source, without prototype mode. The actual guest start callback in this small
fixture is reduced to the identified unlock/exit path; complete Fn216 execution
is exercised separately by ordinary product integration.

Host wake is paused by an isolated callback. The protected case observes the
actual Go handoff wait using runtime.Stack before releasing wake. These scheduling
interventions are absent in production. They are not natural SQL failure
reproductions, occurrence probabilities or a full guest race census.

See [lifetime argument, exact identities and final results](../../../docs/reviews/v050-join-lifetime-fix.md).
