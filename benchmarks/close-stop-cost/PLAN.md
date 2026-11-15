# Finite stop-cost diagnostic
Baseline c680bfe9ccbf80b012fce897c151fe5a7e42d1e3; product f563128520fc49097ac83ef47cdea2dee21ff62a.
Question: which part of pre-cleanup stopping costs time? No shutdown behavior changes.
One instrumented binary, same 48-child fixture and SQL/isolation/disposal checks as #206.
Measure admission, session join, three configuration RPCs, Shutdown start, transport+worker stopped, full cleanup.
P1/cap2 and P2/cap4, synchronous Close, one warmup then three diagnostic repetitions each.
Diagnostic observer overhead is included; not a speedup estimate or engine-only timing.
Budget: 90 minutes execution, 12GiB scratch, 12GiB free reserve. Stop on safety failure.
Report raw events, source identity, reproduction, phase aggregates and limitations. No automatic candidate implementation, whole-suite expansion or adoption.
