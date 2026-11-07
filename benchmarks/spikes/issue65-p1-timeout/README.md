# Issue65 P1-b: native timeout domain

The Human requested continuing after P1-a passed both platforms at candidate
738bbbe58674f097161a1db2c1eda91536e416fe (CI42346396518).
Scope:preserve the public Go QueryTimeout domain in the private native route,
including zero/default30s,positive nanoseconds and MaxInt64 nanoseconds.
Negative durations and overflowing historical millisecond fixture values fail
before starting an instance. Existing SQL/capture admission and guest timer
placement remain unchanged. Public backend wiring remains P1-c.

Private lifecycle profile3 keeps the33-byte header but OPEN.value now carries
positive nanoseconds,not the earlier profile2 integer milliseconds. No fallback.
Guest validates1..MaxInt64 without narrowing. Deadline arithmetic uses unsigned
elapsed nanosecond ticks instead of adding the duration to a signed clock.
The pinned steady clock representation is checked at compile time. A5ms timer
poll remains;nanosecond configuration does not promise nanosecond scheduling.
Historical fixture wrappers explicitly convert milliseconds with overflow checks;
the typed duration constructor uses public defaults and preserves exact values.

Budget:active3h/tooling45min,owned builder/runtime12GiB each,free floor12GiB.
Cheap Go/source mutation tests first,one new guest build and exact worker binding
review,Mac native timeout/ownership and original regressions,then at most one
Linux CI cohort. Preserve original expectations and approved1043 G2 adaptation.
All actual runtime results are pending. No public route,canonical generated
source,consumer/performance or release change is included.


Light checks pass:eight host owner/timeout unit tests under the race detector,
four detected Go timeout mutations and nine detected C++ source mutations with
undefined-behavior sanitizer. C++ checks run both on the extracted source and
again on the actual prepared guest files. Existing ten observation/source guard
commands pass. The first local helper read failed before engine compilation;
the original error is retained and an exact Git-archive tooling snapshot is
used to resume with the same guest source and already verified archives.

Native tests will distinguish exact configuration from scheduling accuracy:
real INSPECT values are decimal strings to avoid float64 precision loss;
MaxInt64 acceptance and PING are checked without claiming a292-year wait.
The first-byte/idle and stale/current command-token cases exercise existing
guest gates. The public Options-default comparison is a focused unit check;
public native backend wiring and inherited Options for Fork/Live remain P1-c.

Zero/default30s here follows Go Options. Existing control-string and Python
option validation are unchanged;no new Python zero-duration acceptance is added.
