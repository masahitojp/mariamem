# Optional lifecycle benchmarks

These scripts measure developer-facing database lifecycle latency and memory
scaling. They are not SQL-engine throughput benchmarks, CI requirements, or
pass/fail performance thresholds. They do not change the product implementation.
The repository-level entry point is `python3 scripts/verify.py bench WORKLOAD [options]`,
where `WORKLOAD` is `ready`, `seeded`, `parallel`, `memory`, or `isolation`.

The historical [0.1.0a1 manual baseline](baseline-0.1.0a1.md) is retained as a
reference. These scripts formalize its workloads; exact reproduction of its
numbers is not claimed because the original full scripts/environment were not
captured. Compare future runs using the same script revision and settings.

## Setup

Install a locally built mariamem wheel into a venv as described in
[development](../docs/development.md). Use the installed package, not `PYTHONPATH`
pointing to source. For the optional Testcontainers comparison:

```sh
.venv/bin/python -m pip install -r benchmarks/requirements.txt
```

Docker must be running and reachable by the Python Docker SDK. These scripts
respect Testcontainers' Docker configuration, including `DOCKER_HOST`. If your
Docker CLI uses a non-default context, configure the SDK endpoint accordingly.
No Docker connection or Testcontainers import is needed for `--backend mariamem`.

```sh
# Fresh DB -> connect -> SELECT 1
.venv/bin/python benchmarks/ready_to_query.py --backend both --runs 10 --warmup 1

# One template preparation, then 10 independent forks; fresh seeded containers
.venv/bin/python benchmarks/seeded_database.py --backend both --rows 1000 --runs 10

# Each trial retains all DBs until every DB returns the expected COUNT
.venv/bin/python benchmarks/parallel_databases.py --backend both --workers 1 2 4 8 --runs 3

# Samples during startup, then holds all ready DBs for 30 seconds
.venv/bin/python benchmarks/memory_scaling.py --backend both --workers 1 4 8 \
  --rows 1000 --runs 3 --hold 30 --interval 0.2

# Short implementation smoke; not a new baseline
.venv/bin/python benchmarks/seeded_database.py --backend mariamem --runs 1 --warmup 0 --rows 10
```

Default backend is `mariamem`. Use `--image mariadb:12.3` (default) or, preferably,
an immutable digest. JSON records the resolved image ID/digests, package versions,
OS/CPU/Python, Git commit/dirty state, and native manifest. Actual MariaDB versions
are recorded per DB. The two backends may run different MariaDB versions.

## Measurement boundaries

- Preflight pulls the DB and Ryuk images if absent and starts Ryuk **before any
  timer**. Container runs use the resolved DB image ID. Concurrent removal of
  cached images during a benchmark is not supported.
- Warmup runs and measurement runs are explicitly labelled and retained as raw
  samples. Summary statistics use only measurement runs. Warmup does not flush
  OS/Docker/runtime caches. Setting `--warmup 0` measures first-use effects too.
- Ready-to-query starts immediately before instance creation and ends when
  `SELECT 1` returns the correct result. Connection readiness polling is included
  (20 ms retry interval, 120 s deadline). Cleanup is timed separately.
- Seeded mariamem prepares a template with an InnoDB table, rows, commit, COUNT,
  disconnect, and cold snapshot. Preparation is recorded, including the source
  DB's shutdown. Warmup and measurement use separate template preparations.
- Each Testcontainers seeded DB starts fresh and creates the same table/rows.
  Schema: integer primary key plus `VARCHAR(64)`; each payload is 32 `x` characters;
  inserts use batches of at most 1,000 rows. This is not a schema/fixture size sweep.
- A fork's ready timing includes restoration, connection, and verified COUNT.
  The sequential report shows both preparation and amortized `prep + ready` cost.
  That sum excludes per-DB teardown; raw cleanup timings remain available.
- Parallel trials start one thread per DB and measure until the last verified
  COUNT completes. Every DB stays alive until the group is ready; teardown comes
  afterward. Per-DB timings and group wall times are both retained. Template
  preparation is reported separately and reused across measured worker counts;
  it is not silently included in each group's wall time.
- A version query occurs after each readiness timestamp. It is metadata work,
  not part of that DB's ready time, but can perturb concurrent work slightly.
- Failures raise an error, clean up owned DBs/containers, and preserve completed
  samples with `completed: false`. Nothing compares a timing to the manual baseline
  to decide success.

## Memory caveats

`memory_scaling.py` retains all independently seeded DBs while sampling startup
and the requested hold period. Warmups only start/query/close; they do not perform
the 30-second hold or memory sampling. Template preparation is outside the sampled
window and is still reported separately. This does not measure template peak memory.

| Backend | Mechanism | Included / excluded |
|---|---|---|
| mariamem | macOS `ps` RSS, summed over benchmark process descendants | Go host and Wasmer trees; excludes Python parent and sampling `ps` process |
| Testcontainers | Docker API `memory_stats.usage`, summed for labelled benchmark containers | Linux cgroup usage including cache; excludes Docker VM/daemon and Ryuk |

**These absolute memory values are not directly comparable.** Do not infer an
exact memory-efficiency ratio. Docker API raw usage can differ from the
cache-adjusted value displayed by `docker stats`. Summed process RSS can count
shared resident pages more than once. OS pressure and reclamation affect results.

The peak is the maximum *observed sample*, not a guarantee of the true instantaneous
peak. `--interval` is a requested delay after each collection: Docker/`ps` overhead
can make the effective interval longer and perturb startup. Each sample retains
its timestamp, collection duration, and per-process/container values. Container
stats are read sequentially, so their sum is not a perfectly simultaneous snapshot.
The ready sample is the nearest observed sample; the last sample may precede the
exact hold endpoint. Compare scaling and transient behavior with those limits.

## Output

Human-readable timings and min/median/mean/max summaries go to stdout. Raw JSON is
always saved under `benchmarks/results/`, or to `--json PATH`. Repository-local
custom paths must also be inside that directory; external paths are allowed.
Warmup samples, preparation, ready/cleanup timings, environment metadata, and
memory time series remain separate. Keep raw output local: it may contain process
IDs, container IDs, and machine-specific errors.

`benchmarks/results/` is ignored by Git and excluded by the source-release file
selector. Scripts, this documentation, and the labelled historical baseline are
source assets. No benchmark is added to mandatory CI.

## 0.2 FAST baseline

Use an installed release wheel and PyMySQL in an isolated environment. Run locally
or on a supported CI runner (macOS 15+ arm64 or Ubuntu 24.04 x86_64):

```sh
python3 -m venv /tmp/mariamem-baseline
/tmp/mariamem-baseline/bin/python -m pip install /path/to/mariamem-0.1.0-PLATFORM.whl pymysql
unset PYTHONPATH MARIAMEM_NATIVE_DIR
/tmp/mariamem-baseline/bin/python scripts/verify.py bench isolation \
  --runs 10 --warmup 1 --workers 1 4 8 --rows 1000 --queries 100
```

`isolation_baseline.py` uses the wheel runtime without checkout imports; an
explicit native override is permitted and recorded. JSON records harness commit
(and dirty state), installed package origin/version, native manifest identity,
actual MariaDB version, settings, warmup/measurement raw observations and p50/p95
(linear interpolation). Generated results stay in ignored `benchmarks/results/`;
use `--json /external/path.json` to retain history elsewhere. No timing threshold
is a pass/fail gate. Failures preserve partial samples with `completed: false`.

Cases are Start→first SELECT, cold Snapshot after InnoDB schema/seed/commit and
disconnect, prepared Fork→connect→first verified COUNT at concurrency 1/4/8,
steady SELECT 1, and SELECT 1 through two simultaneous independent sessions.
Fork is the primary metric: group ready-wall and per-DB latencies are retained,
with separate p50/p95. Snapshot preparation/seed is excluded from Snapshot timing
and parallel-fork timing; phases prepare separate templates. Regression queries
retain each timing; multi-client checks verify session-variable isolation.

Cost collection uses `ps` RSS and cumulative CPU for descendant host/runtime
processes, excluding the Python parent and sampling `ps`. JSON keeps every sample
and collection duration. Peak RSS means **sampled peak**, not exact peak. Ready
incremental RSS subtracts the pre-batch baseline and divides by DB count; this is
not unique physical allocation (shared pages may be counted repeatedly). CPU is
a sampled observed delta, not complete runtime CPU: fast exits and unsampled
startup/exit work are missed, and `ps` time precision varies (Linux can be coarse). Rare PID reuse can alias
CPU observations within a trial. Python process CPU
is recorded separately for the complete lifecycle including cleanup/hold/sampling.
Runtime CPU observations stop before batch cleanup. Sampler failures are recorded;
missing observations yield null rather than fabricated CPU values.

Snapshot-only CPU/RSS are currently unavailable (null): the source exists before
that boundary and exits during Snapshot, making reaped-child CPU attribution
unreliable. This measurement limitation is explicit rather than estimating cost.
Sampling perturbs latency; compare with identical interval/hold settings. Use
`--runs 1 --warmup 0 --rows 10 --queries 5` for an implementation smoke, not a
statistically useful baseline. Testcontainers comparison and profiling come next;
this harness does not select or optimize an isolation architecture.
