# EXECUTE source/unit preflight

This intermediate P2 candidate descends from0ceca7c on
experiment/prepared-execute. `receipt.json` binds the exact tested owner inputs;
`go-tests.txt` and `c-tests.json` retain local results. It is not a P2 completion
or adoption gate. Main, release metadata and canonical generated Go are unchanged.

## Local component verification

Use Go1.26.8 and a C11 compiler with ASan/UBSan:

```sh
python3 scripts/git_identity.py inspect HEAD
go test -race -p 1 -count=1 ./internal/preparedproto ./internal/mysqlwire ./internal/guest
clang -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined \
  -fno-omit-frame-pointer -I guest tests/fixtures/prepared_api_harness.c \
  -o /tmp/prepared-execute-harness
/tmp/prepared-execute-harness
```

The ordinary C run omits the two sanitizer flags. The existing
tests/test_prepared_api.py also checks the unchanged shared P1 envelope golden.
Its mocked C API result remains explicitly labelled `mock API ownership only`;
the extended assertions do not establish embedded engine execution. Go tests use
the saved native12.3.3 vectors and the existing canonical generated runtime,
which does not contain this new C owner.

## Fixed-source CI handoff and remaining gate

Push this child branch to the existing prepared-product workflow. It schedules
the single UNQUALIFIED fixed-source Linux arm64 guest build and macOS arm64 /
Ubuntu x86_64 units. Both development-runtime jobs are **SKIP**, because the
installer still requires P1-only guestc42f1c64… and its exact function/data pins.
This is an explicitly partial source preflight, not a green runtime gate.

Once that new guest exists:

1. Retain its exact source/toolchain/overlay/Wasm record; verify source commit
   using scripts/git_identity.py. Download the unqualified guest, not a cached
   artifact from another commit.
2. Use the formal development translation output to compare complete functions,
   data segments/TLS and handoff changes. Review exact preimages before repinning
   the existing single binding. No alternate guest allowlist or relaxed matcher.
3. Return the reviewed implementation to experiment/prepared-product, whose
   workflow still schedules the complete development gate, then run the P2 probe
   with `--host` and the unchanged native reference. Do not substitute the P1
   probe's successful PREPARE/RESET/CLOSE result for EXECUTE acceptance.
4. Complete the rest of the approved P2 matrix and P3–P6. In particular, uncommon
   parameter descriptors need native/API mapping, temporal SQL modes/ranges and
   reprepare need actual guest cases, and P3 must replace the intermediate
   fail-closed MORE_RESULTS handling with complete typed chains. The current
   source does not advertise PS_MULTI_RESULTS or implement LONG_DATA.

Production implementation scope is already authorized. This handoff is not a
new request for Human approval, a reduced scope, main adoption or Qualification.
