# Issue129: exact public native settings inheritance — first slice

## Bounded implementation record

Question: do public nondefault Options survive Start → Snapshot → Fork → Live
Reset, with the guest retaining the exact fractional QueryTimeout rather than
5000ms? Base source_commit: `a5ee1ed9cc2c6932d317fba77c339b364acd48df`.
Issues65/129 were read on 2026-11-08; their original assertions remain unchanged.
This slice adds fixtures and observation tooling, without changing production
sources, guest patches, canonical generation inputs or historical evidence.

Finite evidence: two explicit nondefault Options vectors; exact host Options
at every owner boundary; actual guest INSPECT timeout_ns through public Go
TCP/Pipe sessions at Start/Fork and TCP at Live generations0/1; inherited-5000ms
negative controls. Exit is prepared fixtures plus focused deterministic source,
unit/race checks. Actual guest/public acceptance is explicitly unexecuted in this
wave and cannot be replaced by fake or unit results. If the shared guest lacks
the unchanged profile3/INSPECT ABI, report that dependency and stop runtime work.

Environment: native macOS arm64, Python3.14 and pinned Go1.26.10. Budget: at most
2 hours active work, 30 minutes tooling, zero guest builds/full runtime staging,
zero broad runtime/benchmark/CI submissions. Worker127 owns heavy guest work.
An inconclusive exit preserves the fixtures and names missing artifact/ABI and
remaining runtime acceptance; it does not close Issue129.

## Integration and execution handoff

`observe.py` adds three files through Go's `-overlay` to an **existing**
`issue65-p1-public/assemble.py` product. It does not stage or install a runtime.
The original public fixture and lifecycle consumers are untouched. The positive
binary retains all existing tests, but this observer selects only the new settings
test; run the original consumers separately for Issue132's complete acceptance.
The staged-only observer methods do not enter production source or public APIs.
Live supports TCP; Start and Fork exercise both TCP and public DialContext/Pipe.

The query vectors are exactly1,234,567,890ns and30,000,000,001ns; startup and
shutdown Options are90,000,000,017ns and20,000,000,019ns. Snapshot stores the exact
Options; it has no running guest to inspect. Each vector produces six records:
Start TCP/Pipe, Fork TCP/Pipe, Live TCP generation0, Reset TCP generation1.
Distinct runtime epochs bind those four phases; integer nanoseconds are strings
in JSON to prevent precision loss. SQL uses an ordinary public endpoint and a
prepared query; INSPECT reads the guest session's deadline while that physical
connection remains open. The child observer only identifies the Live owner.
Startup/shutdown values are checked as inherited host Options, not measured as
elapsed-time expiry behavior.

Worker127/integration needs to provide:

- A native public product at `WORK/temp/public/product`, plus an exact
  `WORK/evidence/public-source.json` inventory with host_source_commit,
  guest_sha256 and binding_sha256. Use the existing checked staging path or its
  explicitly reviewed replacement for127's guest; do not relabel the old C2
  receipt as a new artifact. The native factory and legacy Serve tripwire must
  remain in the staged product. No already-built binary is needed by this tool.
- Unchanged private profile3: READY lifecycle_profile3; OPEN carries positive
  nanoseconds; INSPECT kind9 uses epoch/slot/generation and replies kind102 with
  the same identity and JSON `{"timeout_ns":"<exact decimal>"}`. Frame header
  remains33bytes after its4-byte length. Session capacity is16. Current checked
  worker binding ABI is16/40/44; if127 changes this, provide the new checked
  binding and update staging deliberately before executing these fixtures.
- Working pinned Go1.26.10 and the existing staged module dependencies, plus
  owned `WORK/temp/gocache` and `WORK/temp/gomodcache`. This tool compiles one
  positive test binary and one inherited-5000ms binary against the shared runtime;
  it performs no guest build, translation or installation.

After sharing that artifact and authorizing its execution wave:

```sh
python3 scripts/git_identity.py inspect HEAD
python3 benchmarks/spikes/issue65-p1-settings/observe.py --mode runtime \
  --workspace "$SETTINGS_WORK" \
  --expected-host-source-commit "$SETTINGS_HOST_COMMIT" \
  --expected-guest-sha256 "$SETTINGS_GUEST_SHA256" \
  --evidence "$SETTINGS_EVIDENCE"
```

Evidence output must be fresh. The tool records the complete source receipt hash,
fixture hashes, positive/control binary hashes, all12 exact observations and both
negative detections. The product inventory is checked before/after; temporary
binary/overlay files are disposed. The control preserves the initial Start and
replaces only restored instance timeouts with5000ms. It must fail specifically
at Fork's guest timeout comparison after both exact Start observations; compile,
SKIP, process timeout and unrelated assertion failures do not count as detection.
No Python float is treated as evidence of arbitrary Go nanosecond precision.
Installed Python shared/control exact settings remain a later slice.

## Focused local verification

```sh
python3 -m unittest discover -s tests -p test_issue129_settings.py -v
python3 benchmarks/spikes/issue65-p1-settings/observe.py --mode unit \
  --evidence "$SETTINGS_UNIT_EVIDENCE"
```

The six deterministic Python tests cover observation census, exact values,
runtime identities, false negative-control detections and additive overlays.
The staged Go observer has three focused race tests for reply identity/value
validation, framed request/reply correlation and replacement-child lookup.
These are observer-unit evidence only. The complete public fixture's runtime
compile, both positive vectors, both actual-guest controls, installed Python,
original full lifecycle oracles and both-platform acceptance are **UNEXECUTED**
in this wave. Issue129 and Issue65 remain open.

Initial local outcome: all six Python tests and all three Go observer race tests
PASS, along with Python syntax, Go formatting and affected public-source pattern
checks. Full `scripts/check_public.py` remains FAIL on the same six historical
P1-owner/P1-timeout evidence files reported by C2; none was changed or exempted.
The first two unit attempts stopped before compilation because isolated caches
could not fetch/verify the pinned toolchain without network access. Using the
already-installed pinned Go binary explicitly on PATH resolved that setup issue;
no driver/runtime/oracle modification was involved. Owned local compiler caches
are disposable; only compact verification records need preservation.
