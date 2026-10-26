# Native browser control for the first E2E milestone

Experiment-only executable fixture, not a public adapter. Django and net/http
serve order forms to real Playwright Chromium. Python keeps one app process;
Go starts a new app and native schema per case. The native Python reset is
explicit Django flush plus seed, not an imitation of a mariamem live API.

Prepare an isolated Python3.11 venv with requirements.lock.txt and a normal
mysqlclient build (Connector/C/pkg-config on macOS; libmysqlclient development
files/pkg-config on Ubuntu). Set PLAYWRIGHT_BROWSERS_PATH to owned scratch,
then run `python -m playwright install chromium --only-shell`.
Use the exact image/browser/toolchain in input-manifest.json. Build the Go app
only from a clean committed source, with GOTOOLCHAIN=go1.26.10 and owned absolute
Go cache paths:

```sh
go build -trimpath -o build/e2e-go-orders ./tests/e2e_native_control/goapp
python tests/e2e_native_control/run.py --port PORT --go-app build/e2e-go-orders \
  --expected-source-commit FULL_SHA --output build/e2e-control
```

The supplied native DB must be disposable. The runner creates/drops only generated
e2e-prefixed schemas. Credentials are root/empty on a local test-only server.
Each language runs three real-browser cases. Exactly one intentionally fails
AFTER committing an order; the following case must see only baseline seed.
The parent verifies the exact failure/test name, row observations, PID counts,
HTTP addresses and complete app/schema/browser cleanup. Raw pytest exit1 is
expected here; an unrelated failure, skip or setup error cannot be called PASS.

Run two additional campaigns with `--mutation skip-reset` and
`--mutation restart-app` and separate new output directories. Their real altered
Python lifecycle must be rejected; unchanged Go controls must still pass.
Campaign reports include exact source/Go binary, browser executable and input
hashes. Also retain the Docker image/container identity and native program hash
preflight outside the fixture. Never promote a native-only result to mariamem
compatibility or guest baseline-reset support.
