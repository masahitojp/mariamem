# P5 comparison-gate failure and bounded correction

[Run39760963205](https://github.com/masahitojp/mariamem/actions/runs/39760963205)
tested source_commit `2b697c82cb4326da39d5d5fede4ad7826e3d7711`.
The failing macOS step lacked a corresponding native C-client observation;
it did not establish a new guest behavior difference. Keep P5 open and rerun
the corrected comparison plus the skipped macOS regressions. Native parity
still cannot grant functional acceptance of the Python CALL/NUL failures.

## Confirmed results, not a replacement for P5 acceptance

| Boundary | Result at the tested source |
| --- | --- |
| Both-OS unit jobs / guest-source build | PASS |
| Fresh Ubuntu Python3.14 native observation | Diagnostic matching PASS; prospective Python functionality FAIL retained |
| Ubuntu actual guest observations | Diagnostic matching PASS, Go modes PASS, Python CRUD/typed binary/text controls PASS; CALL FAIL retained |
| Ubuntu installed Python / Go integration, routine and auth controls | PASS; Python17 cases, Go suites retained in evidence |
| Ubuntu existing SQLAlchemy / GORM | PASS; start/fork/fork/start, respectively11 and8 cases per execution |
| macOS actual guest observations | Captured, including Go PASS and Python normal controls PASS; comparison gate FAIL because native C control was missing |
| macOS subsequent edge capture / installed / ORM regressions | SKIP: prior comparison step failed; not relabelled PASS |
| Corrected CI at the new source | Pending submission/result |

Selected raw JSON/logs and original/stored hashes are in
[the evidence receipt](v06x-prepared-p5-ci-evidence/files.json).
Runner/home paths are replaced with placeholders where present; values and
errors are unchanged. Full jobs remain linked at the original run.

## Why the reference was missing

Ubuntu's fresh control selected `MySQLConnection` for default and skipped the
additional explicit C mode. macOS selected `CMySQLConnection` for both default
and explicit C. The previous matcher selected the correct implementation name
but compared against the Ubuntu C SKIP record. Thus `different_cases` was not
proof of a native/guest functional difference.

Ubuntu downloaded the cp314 manylinux C wheel, rather than a pure-only wheel.
The wheel binary requires OpenSSL3.2 symbols while Ubuntu Python used3.0.13;
this is a plausible import-failure cause, not a directly captured import error
from that run. The new environment capture records the actual direct-import
error, extension hash and default availability in subsequent CI. It neither
forces pure mode nor patches the driver/import environment.

An isolated stock Python3.14/OpenSSL3.5 Linux container could import C, but its
C client returned syntax1064/42000, versus the bounded Mac C observation
2006/HY000. The unchanged prospective program stopped at that syntax assertion.
Its [failed comparison](v06x-prepared-p5-ci-evidence/local-matching.json) and
[observations](v06x-prepared-p5-ci-evidence/local-consumers.json) are retained.
This profile is not used to stand in for Mac C; no errors are normalized.

## Corrected reference boundary

The additional fixed native control uses **macOS arm64 Python3.14.8** and the
unmodified Connector26.7.0 cp314 Mac wheel against the same pinned Linux/arm64
MariaDB12.3.3 container. It is not a macOS-native MariaDB server. The original
Python3.11 fixture is retained as historical evidence, not relabelled3.14.

The stock actions Python package was expanded into disposable storage without
system installation. `DYLD_FRAMEWORK_PATH` and `DYLD_LIBRARY_PATH` locate its
unmodified bundled Python/OpenSSL3.5.9 libraries; no connector source, SSL
constants, connection arguments or returned errors are changed. The pinned
archive URL/hash, actual DB image ID, program hashes and reproduction inputs
are in the receipt. Go control uses1.26.8, driver1.9.3 and race instrumentation.

The new [native fixture](../../tests/fixtures/prepared-p5-native-macos314.json)
retains prospective result FAIL at prepared-call in all Python modes. Its
[client profile](../../tests/fixtures/prepared-p5-native-macos314-environment.json)
binds OS/architecture, Python3.14 minor/ABI, Connector version, C-extension hash
and aggregate Python source hash. When the fresh primary reference lacks C,
the matcher requires this second profile and compares it against a newly
captured actual guest client profile. Missing or different identities fail.
Python/OpenSSL patch versions remain recorded separately: the fixture uses
Python3.14.8/OpenSSL3.5.9, while the original Mac CI used3.14.7/3.5.7. The gate
requires the same OpenSSL major/minor series, not identical patch builds; that
is a bounded comparison, not a claim that all dependencies are identical.

Fresh Linux pure/default controls continue to run every CI. The fixed Mac
control is used only when the required actual C client has no fresh C reference.
There is no fallback to a different ABI, Linux C binary, old Python minor,
or shortened oracle. A future client change requires refreshing its native
evidence, rather than accepting mismatched identities.

Replaying the saved Mac guest cases against the new native cases finds **zero
value/error differences**, retaining the full failed CALL observations. This
does not retrospectively verify the old CI client's binary hash (not captured
there); the new CI must exercise the profile binding and remaining regressions.

## Verification and reproduction

Focused Python3.14 checks: **36 PASS**, including wrong/missing native C control,
wrong values/errors,11 client-profile mutations, and CLI profile rejection.
Even successful matching must still emit functional_acceptance FAIL and
human_disposition PENDING. Canonical generated inventory and public-source
checks PASS; runtime, guest, converter, generated source, original consumer
program and strict functional oracle are unchanged.

For the recorded Mac control, download and verify the archive named in the
receipt, unpack it, then use `pkgutil --expand-full` on its Python package.
Expose its framework and bundled library directories with the two variables
above; use an isolated venv with Connector26.7.0/PyMySQL1.2.3. Run the pinned
MariaDB container on a localhost-only port, then:

```sh
python scripts/git_identity.py inspect HEAD
go build -race -trimpath -buildvcs=false -o /tmp/p5-consumer ./tests/prepared_consumer
python tests/v06_prepared_connector_environment.py --require-cext --output /tmp/p5-environment.json
python tests/v06_prepared_consumers.py --native-port 3307 --consumer /tmp/p5-consumer --output /tmp/p5-native.json
# Keep the preceding exit1 / FAIL; it is the prospective functional oracle.
python tests/v06_prepared_consumer_edges.py --native-port 3307 --output /tmp/p5-edges.json
python -m pytest -q tests/test_prepared_consumers_probe.py
```

CI reruns use the existing experiment workflow with the explicit primary and
secondary reference arguments. No main integration, Qualification or release.
