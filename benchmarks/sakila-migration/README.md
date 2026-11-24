# Sakila migration benchmark

The layout follows the [pgmem model-case](https://github.com/shibukawa/pgmem/tree/postgresql/18/bench/modelcase) within this repository's `benchmarks/` directory.

```text
benchmarks/sakila-migration/
├── run.sh              Build the test and driver, run the comparison, and render results
├── cmd/driver/         Start each backend and measure the test suite
├── internal/trace/     Timing schema shared by the suite and driver
├── store/              Sakila fixture, migration SQL, and correctness tests
├── docker/             Pinned MariaDB image recipe and Linux test environment
├── summarize.py        Validate samples, compute medians, and draw the timeline
└── results/            Dated reference and local runs
```

## Reference results

Measure the same eight late-fee migration cases with the [pgmem model-case timeline](https://shibukawa.github.io/pgmem/benchmarks/#model-case-suite-one-test-suite-two-execution-models) as a reference. Every trial uses one build of the pinned [Sakila migration suite](store/migration_test.go) and reports MariaDB 12.3.4. The test flag is `-parallel=8`. mariamem uses a Snapshot and eight parallel Forks. The three server arms use one application database, eight serial cases and seven resets each.

Both the controller and the test binary run in the same Linux arm64 Docker Desktop VM. The native process runs directly in the controller container with preinitialized, disk-backed system data. Testcontainers and `docker run` start fresh sibling containers with the same official-image-derived MariaDB build, including system database initialization and application database creation inside the measurement. Testcontainers launches its Ryuk reaper in each fresh controller process, and uses tmpfs and relaxed InnoDB commit flushing. The `docker run` server uses disk-backed storage and normal commit flushing. TCP is used for all arms, including the container arms on one private Docker bridge. Image pulls, build, and controller-container startup are outside the measurement.

One warm-up per arm is excluded and the starting arm rotates over five measured runs. The saved reference includes all 24 suites and uses the original timing boundaries. It measured mariamem SQL readiness from inside the test process and included driver-side report parsing in the external modes. New runs measure mariamem SQL readiness from child process launch and end the test interval at child process exit for all four modes.

| Median, ms | mariamem | Native MariaDB | Testcontainers | docker run |
|---|---:|---:|---:|---:|
| Boot to application SQL | 69.5 | 129.4 | 3,926.7 | 4,935.6 |
| Fixture | 26.9 | 23.1 | 7.5 | 25.8 |
| Seven resets | — | 100.2 | 22.4 | 86.6 |
| Test process | 213.4 | 226.6 | 77.5 | 215.0 |
| Boot plus test binary | **213.4** | **356.9** | **4,004.4** | **5,143.4** |


All 24 suites passed on 2026-11-22 JST, using Go 1.27.4 and Docker Desktop 29.9.3 on macOS arm64. Startup accounted for 3.93 s of the 4.00 s median Testcontainers run and 4.94 s of the 5.14 s median Docker run. With the server ready, the Testcontainers test process took 77.5 ms under its tmpfs and relaxed commit-flushing settings. That timing reflects both settings together.

## Run

From the repository root, run the comparison with Go, Docker Desktop on arm64, and a Python environment containing Matplotlib 3.9.4. The runner mounts the Docker socket in the controller container to launch sibling containers. Before timing, the runner builds the MariaDB 12.3.4 image using the pinned recipe and verified packages. It uses the build's image ID for all launches and records that ID with each sample. It fetches the pinned Docker CLI and Ryuk images when needed.

```sh
./benchmarks/sakila-migration/run.sh
```

By default, the script runs one warm-up plus five measured suites per mode and writes `samples.jsonl`, `median.csv`, and `benchmark.png` to `results/latest/`. Set `RUNS=1` for a short check, `RESULTS_DIR` to save results elsewhere, or `PYTHON` to select a virtual environment's interpreter.

The default runtime is Git commit `3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d`. `SAKILA_RUNTIME_REF` can select a different committed revision that reports MariaDB 12.3.4. The runner checks Git identity and builds the tests in a temporary source archive. The table above is from the original run, using the Sakila fixture adapted from `0766a97375f3ee2b1c524cde4289e699e50ec1fc`.

To recalculate medians and draw a chart from the reference samples, pass the path to a local sample file and an output directory.

```sh
python3 benchmarks/sakila-migration/summarize.py   /path/to/local/samples.jsonl /path/to/output
```
