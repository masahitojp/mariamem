# Released direct-link consumer cost

`measure.py` obtains the **public** `github.com/masahitojp/mariamem@v0.4.0`
through ordinary Go module resolution and sum verification. It creates a fresh
external project with no `replace`, runs public Start/SELECT/CRUD/Close, and
measures acquisition separately from compilation. It changes no production code.

macOS runner example (Go 1.26.8 must be available):

```sh
task_work=$(mktemp -d)
python3 benchmarks/spikes/consumer-cost/measure.py \
  --work "$task_work/consumer-cost"
```

Run without competing CPU/memory-heavy work. During a fan-out investigation, wrap
the **whole** command in the shared exclusive measurement lock. The runner uses
the installed Go 1.26.8 executable so its isolated module cache does not include
a second toolchain download. It preserves ordinary CGO/default parallelism.

The resulting `result.json` records commands, environment, module origin/sums,
sizes and log checksums. Logs, module/build caches and binaries are disposable
work artifacts. Preserve only small sanitized results and the report in Git;
keep raw evidence outside the source checkout. The runner deliberately requires
a new work directory to prevent accidental warm-cache contamination.

## Boundaries

- Two independent empty-cache `go build` trials; OS page cache is not flushed.
- Independent empty-cache `go test`, then cached and `-count=1` warm tests.
- Warm builds and a consumer-only marker edit used by both main and test.
- Normal/stripped binary sizes, with a database/sql + MySQL-driver control.
- Cache sizes include logical bytes and `du -sk` allocated bytes.
- macOS `/usr/bin/time -l` maximum RSS is not aggregate simultaneous compiler
  memory. No minimum-RAM or Linux performance claim follows from that number.
- Actual SQL test execution is included in executed-test wall time; cached test
  results are reported separately. Acquisition includes local extraction/checks
  and network time, with one trial; it is not a general network-speed guarantee.

No generated-source edits, build parallelism restriction, compiler workaround,
module split, executable cache or runtime architecture change is made.
