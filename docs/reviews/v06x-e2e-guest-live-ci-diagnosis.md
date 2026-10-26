# Guest E2E CI40299270893 — macOS startup failure

[Run40299270893](https://github.com/masahitojp/mariamem/actions/runs/40299270893)
is FAIL on exact16eb116d8056581364f3a609f9b97f885796e040. Ubuntu's job succeeds.
On macOS arm64, focused26 tests, the Go browser parent assessment and both real
SQL live controls pass. Python3.11.9 fails all three browser fixture setups:
the Django child does not respond to its health check within30 seconds.
Python3.14 is not reached. The child remains alive until teardown and exits on
SIGTERM; relay/host cleanup succeeds. Its app log is empty. This evidence does
not yet identify whether startup is blocked in Python/Django, networking or SQL.
It is not evidence of a Homebrew/OpenSSL linking failure.

The original macOS artifact12640435588 is retained losslessly with its verified
GitHub SHA256 under
[the receipt directory](v06x-e2e-guest-live-evidence/ci-40299270893/assessment.json).
The original PASS/FAIL scope and source are preserved.

The next candidate enables unbuffered Python child output and an opt-in,
test-only `sitecustomize` diagnostic. It emits its PID/interpreter and dumps all
Python thread stacks every10 seconds, allowing two snapshots inside the unchanged
30-second startup deadline. A real subprocess test verifies stack output, normal
exit and inactive opt-out. The native application/migrations/browser files,
product code, SQL, startup timeout and acceptance oracles are unchanged.
This is a diagnostic candidate, not a claimed fix for the startup failure.
The existing two-platform CI will build exact new source and provide the next
observation; do not relabel the earlier local PASS or failed CI as that source.
