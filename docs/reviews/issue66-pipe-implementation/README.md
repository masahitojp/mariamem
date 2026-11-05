# Issue66 opt-in Go Pipe candidate: implementation evidence

2026-11-05. Candidate work follows the Human's request to continue the finite
[spike](https://github.com/masahitojp/mariamem/tree/8f5ef18a1adf7219866ceaf03a1011e430bd6bba/benchmarks/spikes/net-pipe).
This records implementation/verification, not main adoption or release approval.

## Result and contract

The candidate adds `Database.DialContext(ctx, network, address)` for direct use
as MySQL Config.DialFunc, and `mariamemtest.Options.InProcess` for helper-owned
preparation/child pools. Default and external-command DSNs remain TCP; listener
startup, guest/generated sources, wire handlers and version metadata are unchanged.
Only tcp/tcp4 with the receiving Database's exact endpoint are accepted, so a
connector cannot silently redirect another target. Live's public endpoint remains TCP.

Successful TCP/Pipe connections reserve the same bounded guest slots under the
same admission/shutdown lock. Pipe rejection returns a local HostError before
starting a worker; a full server matches ErrCapacity without invalidating it.
TCP retains protocol1040. Closed/consumed databases match ErrClosed; failed
instances match ErrUnusable, with the underlying failure retained. Dial's context
controls admission; later I/O belongs to the driver/connection deadlines.

This resolves the spike's unbounded rejection-worker issue without adding a
second queue or rejection-worker budget. The public Database mutex serializes
Dial with Close/capture. A returned raw pipe is already registered as busy;
closing/capturing the owner joins session cleanup before releasing resources.
Forks own independent dialers/pools, and the fixture closes pools before capture
or child disposal. External migration commands can still use the supplied TCP DSN.

## Identity and checks

Baseline source_commit `c27061f1a33eed2908fd90b0e2d816692e001339`.
Locally verified source_commit `3d5a5ce8cc3a91e8233181b4476031f7180e2b6d`.
A clean standalone clone was checked with scripts/git_identity.py before builds;
these later documentation/evidence files were not part of that executable source.
Go1.26.10, Apple M1 / macOS27.2 arm64, Python3.11.18, mysql driver1.9.3.
Owned storage budget6GiB, minimum free8GiB. No installed/release artifact claim.

- Standard `scripts/verify.py check --profile daily`: PASS. Includes normal Go
  unit/vet, generated-input checks,67 early source tests, and remaining Python
  tests1847 PASS /98 existing skips, plus92 subtests.
- Standard `scripts/verify.py smoke`: PASS. Existing Python/Go Live controls and
  four bounded TestInProcess top-level cases passed. The latter adds about2s of
  actual test execution on this host; CI cost is unmeasured. No new CI job/matrix.
- Focused race on public Pipe lifecycle/fixture and host admission: PASS with the
  commands below. Generated `code/p0` through `code/p8` packages were deliberately
  excluded from race instrumentation; SDK/driver/host/fixture and other packages
  retain it. Actual generated guest execution remains in the tests. This does
  not claim race qualification of generated engine internals.

```sh
go test -p 1 -vet=off -race \
  -gcflags='github.com/masahitojp/mariamem/internal/generatedgo/code/p...=-race=false' \
  -tags integration ./tests/godefault -run '^TestInProcess' -count=1 -v -timeout 120s
go test -p 1 -vet=off -race \
  -gcflags='github.com/masahitojp/mariamem/internal/generatedgo/code/p...=-race=false' \
  ./internal/host ./mariamemtest -run 'TestRejectedPipe|TestInProcessPool' \
  -count=1 -v -timeout 60s
```

Coverage includes mixed TCP/Pipe use; explicit prepared parameters; autocommit persistence and
transaction rollback; raw-handshake capture refusal; consumed parent refusal; Fork data
isolation/sibling availability;16-session capacity and1,000 rejected local dials;
TCP1040; unread handshake and concurrent Close; query deadline/instance failure;
fixture preparation and fresh per-test state. A unit stress performs2,048
concurrent rejected dials without registering clients or starting workers. A
connector test verifies the fixture actually selects the owner's dialer and
keeps TCP when disabled.

## Retained attempts and remaining limits

The first daily attempt stopped on two source/policy failures: the new root test
file was not in the explicit public allowlist, and the smoke owner expected
three commands. Tests were moved into the existing root owner; the smoke contract
now explicitly requires the fourth bounded consumer. The allowlist and test
oracles were not broadened/relaxed. Normal Go tests had passed in that attempt.
The original all-generated-engine race compile was interrupted before execution
because it exceeded the intended changed-boundary scope; it is not a PASS or a
runtime failure. Compact check dispositions are in checks.json; original logs
and initial source identities remain in local durable evidence.

Ubuntu and protected PR checks remain pending at submission. Full Release,
installed artifacts, all-engine race, whole-process RSS/goroutine campaigns,
new performance measurements and concurrent-load throughput are unexecuted.
The original spike's allocation increase remains a material tradeoff; its timing
numbers are not measurements of this public API candidate. Candidate adoption
and subsequent release approval remain separate decisions.
