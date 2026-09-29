# Fixed-reference repeated isolated-test comparison

## Method

This benchmark compares practical workflows, not equivalent engine internals or
an unconditional winner. Primary venue is the same Apple M1 MacBook Air / 16 GiB
macOS 27.0 reference used by final v0.2 FAST acceptance. Docker Desktop is already
running; image download and Go compilation are outside timed suites. Record its
VM CPU/RAM allocation and existing background container count, not merely host RAM.
No DB cache settings, durability or auth configuration is changed for either side.

Use the existing synthetic migration (one CREATE TABLE) and 1,000-row / 32-character
InnoDB fixture; this is not a complex application migration or ORM integration.
Each isolated test verifies count/payload and mutates a row. The next test must
observe the pristine row, so reset failures fail the measurement, not disappear.
The Testcontainers MariaDB module uses its normal startup/readiness/connection
path with no container reuse. Migration SQL and test SQL match both backends.

| Condition | Isolation boundary | Preparation |
|---|---|---|
| mariamem-fresh | Fresh guest/runtime/server and schema per test | Start + migration/fixture every time |
| mariamem-prepared | Fresh guest/runtime/server per test from cold Snapshot | Start + migration/fixture + Snapshot once per suite, included in total |
| testcontainers-fresh | Fresh MariaDB server/container/data volume/schema per test | Run + migration/fixture every time |
| testcontainers-schema-reset | One server/container per suite; fresh schema and client pool per test | Run once, then DROP/CREATE schema + migration/fixture per test |

Schema reset does not reset global variables, plugin state, engine caches, users,
server settings or unrelated schemas. It is not equivalent to a fresh server.
Transaction rollback is another weaker boundary: it does not generally undo
DDL/nontransactional or global/session effects; it is discussed, not mixed into
these results. Reusing a container across suites further changes lifetime and
state guarantees; it is not enabled here.

The main measurement uses 10/50/100 sequential isolated tests, three independent
suite trials per condition/count, rotating condition order. One separate 1-test
warmup per condition is labelled and excluded. All measured suites/tests are
retained. Three suite repetitions expose one-off noise but their interpolated
p95 is descriptive, not a strong tail estimate. Per-test samples are correlated
within a suite. Suite totals include actual preparation, allocation, test SQL and
cleanup, plus explicitly recorded resource-observer/checkpoint bookkeeping.
They do not multiply an isolated-startup median to fabricate a suite duration.

Memory is observed at first/last ready state (every fresh-container ready state),
with OS high-water marks and cgroup v2 memory.peak where available. Runtime RSS,
Go host RSS and container cgroup usage/peak are distinct scopes; container values
exclude the shared Docker VM/daemon. Resource observation cost is recorded and
must be considered especially for fast schema resets. CPU includes runner SELF,
waited local child CPU and container cgroup CPU where observable; teardown edges
and auxiliary processes prevent an exact apples-to-apples total.

The official image 13.1.0 lookup failed, whereas the embedded server identifies
itself as 13.1.0. The arm64 official 11.8.9 platform manifest is pinned in
`practical-suite-inputs.json`. It runs natively inside Docker's Linux arm64 VM;
no amd64 emulation, special init scripts, reduced caches or tmpfs shortcut.
This version/default-configuration difference must remain explicit.

## Run

```sh
GOTOOLCHAIN=go1.26.8 .venv/bin/python benchmarks/practical_suites.py \
  --native-dir build/fixed-reference-native/mariamem-native-darwin-arm64 \
  --runs 3 --counts 10 50 100 \
  --json benchmarks/results/practical-suites.json
```

The script validates all native hashes and native arm64 image identity before
execution. Raw suite reports/logs and aggregate JSON remain ignored in
`benchmarks/results/`. A failed SQL/correctness/cleanup step fails the run;
missing suite/test evidence cannot silently contribute to a passing summary.
Owned DB-container IDs are checked absent after completed suites. It does not
stop unrelated containers or alter mariamem product behavior.

## Results

Pending fixed-reference measurement. Do not reuse historical Ubuntu numbers as
if they were local or as if fixture-ready isolation meant the same lifecycle.
