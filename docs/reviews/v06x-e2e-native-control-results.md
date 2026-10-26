# First executable E2E result — native Django and Go browser controls

The first runnable control now exists. Both applications completed real Chromium
form actions against native MariaDB12.3.3. Python retained one Web process and
HTTP endpoint across three sequential cases; Go used a new child process/schema
per case. The deliberate post-commit test failure was followed by a case that
saw only baseline seed, and app/browser/schema cleanup was verified. Two actual
lifecycle defects were also injected and detected.

This is a concrete input for reviewing the next live experiment. It does not
establish mariamem browser support or guest stable-endpoint reset: the Python
reference reset uses recorded native Django flush/reseed. Recommend keeping this
app/browser contract as the initial target, running the same fixture on native
Ubuntu CI, then designing the minimum mariamem live/reset experiment against it.
The strongest limitation is that this local server was an amd64 Linux container
under Docker Desktop on macOS arm64; no native Ubuntu-host or native macOS-server
result is inferred from that topology.

## Pinned executable and evidence

Experiment source_commit: `0776d7a368a1e162e3884bec9a84b23031ad8e59`, branch
`experiment/e2e-native-control`. Source and fixture/input hashes are in the raw
reports. The test-only files are under `tests/e2e_native_control/`; the selected
commit can be inspected directly on
[GitHub](https://github.com/masahitojp/mariamem/tree/0776d7a368a1e162e3884bec9a84b23031ad8e59/tests/e2e_native_control).

[Assessment](v06x-e2e-native-control-evidence/assessment.json),
[acquisition](v06x-e2e-native-control-evidence/acquisition.json),
[checksums](v06x-e2e-native-control-evidence/SHA256SUMS.json) and the lossless raw
ZIP in base64 preserve the observations. Decode the archive before checking its
original raw_archive_sha256. It includes pytest XML/output, event streams and
app logs, as well as earlier failures under their original source identities.
No archive is represented as a GitHub artifact; this is a local control receipt.

| Input | Observed local value |
| --- | --- |
| Test/browser/application host | macOS arm64; Python3.11.17; Go1.26.10 |
| Native DB server | Linux amd64 MariaDB12.3.3-ubu2404, Docker Desktop CPU emulation |
| Server image | mariadb@sha256:2f4f46f80e7251990bfdc601ae3f7f2964ddb4dc1868f7deca699fc1ece8c35e |
| Native executable identities | mariadbd, mariadb and mariadb-dump versions, ELF architecture and hashes match the existing pin; image ID matches |
| Python app | Django5.2.8 normal mysqlclient2.2.7 MySQL backend; two real Django migrations and seed |
| Native Python client library | MariaDB Connector/C3.4.11; compiled module hash retained in each raw report |
| Go app | net/http and go-sql-driver/mysql1.9.3; ordinary sql.DB and prepared-by-default parameter path |
| Browser | Playwright1.56.0; Chromium headless shell141.0.7390.37, revision1194; executable hash retained |
| Budget | 3GiB owned scratch,8GiB minimum free,900s campaign ceiling; DB container1GiB/two CPUs |

Local requirements.lock.txt records the actual installed dependency set. No
PyMySQL compatibility substitution was used. Installing pkgconf and
mariadb-connector-c was necessary to build normal mysqlclient on this host; this
is not a cold-setup timing/cost result. Python3.14 and native Ubuntu are scheduled
CI cells, not local PASS. Other browsers, multiple workers, background jobs,
Django TestCase/pytest-django and post-startup capture remain unexecuted cells.

## What the browser actually did

The shared workflow is an order form, with SKU/quantity fields, a Save action and
visible ordered rows. Python retains CSRF handling; browser DOM actions submit
the form and follow the application's redirect. Go has its own ordinary HTTP
application and native schema setup. Their observable UI contract matches;
there is no claim of complete framework/schema equivalence.

1. Before each case, the browser and a direct DB observation see only
   `SEED:2:ready`.
2. Case01 submits `ORDER-A`, commits through the application and observes both
   seed and the new order.
3. Case02 starts from seed, submits/commits `FAILED-A`, then deliberately raises
   `E2E_EXPECTED_FAILURE_AFTER_COMMIT`.
4. Case03 must again see only seed. The parent requires exact XML test/failure
   counts and name/message, row transitions, PIDs and complete cleanup.

Each positive language subprocess therefore reports exactly two passed tests
and one intentional failure (exit1). The independent parent accepts that precise
failure-control result. An unrelated timeout/setup failure, skip, incorrect row
or missing cleanup cannot become native control PASS.

## Results and actual defect injections

| Campaign | Python observation | Go control | Parent judgment |
| --- | --- | --- | --- |
| final-control | One app PID/start, same HTTP URL, three native resets; A's committed changes absent from B | Three independent child PIDs/schemas, correct rows and graceful exit0 before schema removal | PASS_NATIVE_CONTROL |
| skip-reset | Actual reset is omitted. ORDER-A remains; next two cases fail setup with the observed stale rows | Unchanged strict Go control passes | MUTATION_DETECTED |
| restart-app | An additional Python app is really launched per case. Row/failure tests still behave correctly, but four starts and three case PIDs/HTTP URLs violate retained-app ownership | Unchanged strict Go control passes | MUTATION_DETECTED |

The mutation assessor requires those specific row/lifecycle signatures and
complete cleanup, not merely any nonzero exit. Three focused oracle tests
additionally reject changed data, missing cleanup/readiness/browser close,
skips/errors, unrelated failures, process restart and missing reset.

All test schemas were confirmed absent afterward. Browser/app shutdown is
recorded in the event streams; Docker container disposal is a separate local
cleanup receipt. This verifies reference-workload cleanup, not forced mariamem
host-failure containment.

## Corrections preserved rather than relabeled

At29c8515 the Go browser control passed but the Python app's default form-label
suffix did not match the intended accessible selector. Two unexpected browser
timeouts remained FAIL. The authored Django form was corrected to render the
specified label; selectors and outcome assertions were not weakened. Source
b1734d3 then passed both controls. The final0776d7a adds exact mutation evidence;
all three final campaigns ran on that new clean source.

A first Go build from a linked worktree embedded parent source3b22a88 rather than
the experiment commit. scripts/git_identity.py rejected it before campaign
admission. A clean independent checkout at each exact experiment SHA was used to
build the application, and the resulting compiler/revision/clean flags were
verified. The original failure console and source-specific control reports are
retained. The source identity guard was not bypassed or changed.

The initial workspace runner's failure cleanup also required an inspected
reproduction record for Playwright's opaque ICU/browser distribution. Its hashes
and package/revision recipe were recorded. Subsequent manually supervised runs
used the documented experiment_disk.py guard; source/results were not deleted to
hide that setup failure.

## Reproduction and next comparison

Use an independent clean checkout at0776d7a so Go VCS stamping binds the actual
source. Follow the fixture README, install its lock into an isolated Python3.11
venv, provide the pinned disposable MariaDB image on localhost and install the
matching Playwright headless shell. Use owned absolute cache/browser paths:

```sh
GOTOOLCHAIN=go1.26.10 go build -trimpath -o build/e2e-go-orders ./tests/e2e_native_control/goapp
python tests/e2e_native_control/run.py --port 3307 --go-app build/e2e-go-orders \
  --expected-source-commit 0776d7a368a1e162e3884bec9a84b23031ad8e59 --output build/e2e-positive
python tests/e2e_native_control/run.py --port 3307 --go-app build/e2e-go-orders \
  --expected-source-commit 0776d7a368a1e162e3884bec9a84b23031ad8e59 --output build/e2e-skip-reset --mutation skip-reset
python tests/e2e_native_control/run.py --port 3307 --go-app build/e2e-go-orders \
  --expected-source-commit 0776d7a368a1e162e3884bec9a84b23031ad8e59 --output build/e2e-restart --mutation restart-app
```

Output directories must be fresh. The supplied DB is disposable; generated e2e
schemas are created/dropped. `.github/workflows/e2e-native-control.yml` executes
these native controls on Ubuntu24.04/Python3.11 and3.14 with original native
acquisition guards and source-stamped Go app. Its results are new evidence when
they execute, not a relabeling of the local Mac-host control.

The next architectural question is now testable: can mariamem satisfy the same
Python PID/endpoint/row contract while preserving its ownership and failure
rules? Go's per-test child/configuration path can be compared using existing
Fork first. Do not introduce a general Django adapter or promise physical-session
preservation merely to obtain a green browser test. Review the exact reference
app and minimum target before selecting a live mechanism.

## Native CI submission correction

Initial [run40285909685](https://github.com/masahitojp/mariamem/actions/runs/40285909685)
at0776d7a was rejected before any jobs ran. Its workflow used runner.temp in a
job-level environment expression. Source3446b5c927239542fb4203d5c6b4a4342c6b4984
changes only that workflow: an owned relative browser directory replaces the
expression, and the disk guard includes browser scratch. YAML/path checks pass;
the next CI run must establish GitHub acceptance and native execution. The
[first-attempt record](v06x-e2e-native-control-evidence/ci-first-attempt.json)
distinguishes the inferred configuration diagnosis from unavailable detailed
GitHub annotations. Local results remain bound to0776d7a, not the new CI SHA.

## Ubuntu CI result — exact3446b5c

[CI40286173347](https://github.com/masahitojp/mariamem/actions/runs/40286173347)
now passes both native Ubuntu24.04 jobs: Python3.11.17 and3.14.8. Each executes
Python/Go positive controls plus the two real Python lifecycle defects. The
[new assessment](v06x-e2e-native-control-evidence/ci-40286173347/assessment.json)
verifies original artifact digests, raw XML/events, source/Go identity and exact
defect classifications. Earlier local results remain bound to0776d7a.
The [reference review](v06x-e2e-native-control-review.md) recommends using this
fixture for the next mariamem comparison, with native-versus-live limits explicit.
