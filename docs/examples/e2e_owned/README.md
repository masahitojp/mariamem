# Owned E2E entry candidate

These are source-build examples for the proposed EP1/EG1 entry. The implementation
is a candidate, not an adopted/released support claim. The
[decision](../../decisions/e2e-entry-implementation.md) records implementation
approval and its probe condition; #18 owns full acceptance.

- [Python Django/browser example](python/test_orders.py): one `BrowserEntry` per
  fixture worker and one fresh browser context per `entry.case(browser=browser)`.
- [Go HTTP example](go/entry_test.go): `NewHTTP` on the parent test, then
  `Case(t)` inside each sequential subtest. A lease lasts until subtest cleanup,
  including Fatal/Goexit and parallel suspension. Use independent owners for
  parallel tests; a same-owner overlap fails before hooks or Reset.

The supplied entry starts its source, calls `prepare(source)` once, disconnects
preparation sessions, captures a baseline and creates Live. Preparation must
finish migrations/seed and close its application connections/processes before
returning. No automatic app-framework routing or command discovery is performed.

`start_ready(ctx, target, register)` / Go `StartReady` receives the actual Live
connection target. Start only against that target. Immediately register a partial
app handle after allocation, then check readiness and return that registered
handle. Its `identity` / `Identity()` and `base_url` / `BaseURL()` describe the
stable app. Required hooks are `quiesce_and_retire(ctx)` / `QuiesceAndRetire` and
`stop_reap(ctx)` / `StopReap`. Go app handles must be non-nil/comparable (normally
pointers). Duplicate registration is rejected; a rejected newly created handle
still needs its hook to clean it up locally.

Before every case, including the first: exclusively admit setup, quiesce/join
application work, close every physical SQL connection, Reset, verify target/app
identity and generation, optionally Resume, reset external state, create case
resources, then admit body. Live independently checks physical disconnect. An
idle pool also prevents Reset. No registered background work may restart between
quiescence and admission. Optional Resume is required unless configuration
explicitly declares that the harness is the sole source of work.

The examples keep the unchanged fixed Django/Go orders apps and their migration/
SQL inputs. They use the sole-work-source model with CONN_MAX_AGE=0 / Go
MaxIdleConns(0); completed requests release physical DB sessions. A different app
must supply hooks for its own pools/jobs. Neither hook success nor zero sessions
proves absence of arbitrary future unregistered work.

Python `external_state(ctx, app, register)` and Go `ExternalState` may register
additional case resources for reverse-order close. Register immediately after
creation, before the next operation can fail. Their close methods must finish/
join work, not just launch shutdown. The browser and browser installation remain
caller-owned; the case owns each new context/page. Go case Client tracks and
closes response bodies and cancels/joins requests at cleanup. Background work
outside that Client must be registered and joined by the application.

Ordinary assertions keep their framework behavior and permit the next fresh case
when cleanup succeeds. Setup/Reset/identity failure or case cleanup debt latches
owner failure and stops future admission without implicit retry. Close attempts
app shutdown before Live/baseline/source and preserves original plus cleanup
failures. Python interrupt identity remains primary with cleanup failures chained;
ordinary combined failures retain original objects in exception groups. Go errors
retain causes via Unwrap/errors.Join. Hook cleanup panic is an HTTPPanic retaining
the panic value, and other cleanup attempts continue.

Budgets are cooperative: setup/reset120s, drain5s, cleanup30s by default. Go zero
selects defaults; negatives reject. Python requires positive finite values. No
hook thread/goroutine is forcibly stopped. Live/Snapshot cleanup can outlast its
deadline. Close during an active Python case on that thread is rejected; another
thread waits within its cleanup budget and reports uncertainty on timeout. Go
teardown belongs to the common parent, after case cleanups; no public concurrent
Close API is added. A hook must not reenter owner/case lifecycle methods.
Repeated completed owner cleanup preserves its first outcome. Do not reuse failed
owners, share endpoints across parallel cases, capture app-start writes into a
new baseline or infer delayed-job fencing/session continuity.

## Run actual examples

Build in a clean exact checkout and inspect its source identity first. Use the
existing fixed E2E dependency lock and Playwright browser acquisition described
in the [Live examples](../live/README.md). No new dependency is added to the SDK.

```sh
python3 scripts/git_identity.py inspect HEAD
go build -p 1 -trimpath -o build/go-live-orders ./tests/live_acceptance/goapp
go build -p 1 -trimpath -o build/mariamem-host ./cmd/mariamem-host
E2E_OWNED_RUNTIME=1 E2E_GO_APP="$PWD/build/go-live-orders" \
  go test -p 1 ./docs/examples/e2e_owned/go -count=1 -v
PYTHONPATH=python E2E_OWNED_RUNTIME=1 MARIAMEM_TEST_HOST="$PWD/build/mariamem-host" \
  python -m pytest docs/examples/e2e_owned/python/test_orders.py -q -s
```

The Live workflow runs these examples on both hosts, and Python on both minors,
with the existing native/defect controls preserved. Existing receipt claims remain
bound to their original sources. Functional example PASS alone does not complete
the hook-failure, installed-consumer and bounded usability evidence required by
#18. The [current sequencing decision](../../decisions/e2e-v060-work-sequencing.md)
places detailed resource characterization in shared v0.7.x work. No release or
performance result is implied by these commands.
