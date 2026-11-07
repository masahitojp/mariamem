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
