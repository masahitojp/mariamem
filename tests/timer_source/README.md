# Canonical timer source controls

Normal `verify.py check` runs `tests/test_timer_source.py` without downloading
source. A C++17 compiler and patch are required; missing tools fail this owner.
The complete upstream fixtures preserve MariaDB copyright/license headers.
`inputs.json` pins their MariaDB commit and SHA256. Only the two timer hunks
from `guest/source.patch` are applied with fuzz0; fixture or patch drift fails.

The controlled-clock methods/initializer and negative controls were promoted
from `benchmarks/timerselection/check.py` and
`benchmarks/timercalibration/check.py` at reviewed commit
`d24087eedd21c6384c231fb119c8e98da7b370aa`. Six SQL selection observations /
two mutations and ten initializer profiles / four mutations remain required.
These are source units, not real guest or performance evidence.

Normal `verify.py integration` separately runs
`TestAnalyzeTimerFreshAndFork` against the generated product on TCP and Pipe.
It rejects zero/missing/implausible delayed-query timings, verifies following
SELECT and isolated child data, and checks Close/WaitDisconnected errors.
