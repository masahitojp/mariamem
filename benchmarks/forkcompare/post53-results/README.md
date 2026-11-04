# Post-#53 pgmem comparison evidence

See [report](../../post53-pgmem.md). This cohort repeats the original48-child
P4/P8 TCP workload, with current mariamem main and pinned pgmem v1.18.2.

- compact.json/summary.json/summary.csv: twelve ordinary runs, checked phase
  summaries and memory sample metadata. Raw child/sampler files are projected,
  not silently presented as retained originals; their hashes are in compact.json.
- pilot.json: both positive/negative seed pilots and sampler ABI sanity check.
- historical-summary.json: old cohort, never pooled with the new one.
- control/: separate interleaved v0.6.0/main control,16 runs (12 ordinary /4
  warmup); raw-result hashes, checked oracles/phase maxima, CPU/wall/RSS records
  and actual alternate-modfile binding. No pgmem runs in this later cohort.
- plan.json,source-pins.json in the parent module, inputs inside compact.json,
  original-harness SHA and declared dependency mapping identify exact inputs.
- run.py/campaign.py: wrapper used around the unchanged Go harness. The published
  campaign takes source checkout argv[1] instead of a local workspace path;
  publication.json records the executed/published recipe hashes separately.
  It also records original/published compact hashes for normalizing the local
  Go module-cache prefix in dependency metadata; result values are unchanged.
- SHA256SUMS.json: all retained files in this directory, excluding itself.

Read-only validation, independent of deleted temp/build/raw:

```sh
python3 benchmarks/forkcompare/post53-results/analyze.py --results benchmarks/forkcompare/post53-results --check
```

Same-session control median verification, from this directory:

```sh
python3 - <<'PYCODE'
import json,statistics
from pathlib import Path
p=Path('control');r=json.loads((p/'records.json').read_text())
assert len(r)==16 and json.loads((p/'completion.json').read_text())['result']=='PASS'
for row in json.loads((p/'summary.json').read_text()):
    selected=[x for x in r if not x['warmup'] and x['backend']==row['backend'] and x['parallel']==row['parallel']]
    assert len(selected)==3
    for k in ('wall_ms','cpu_ms','peak_rss_bytes'):
        assert statistics.median(x[k] for x in selected)==row[k]
PYCODE
```

For remeasurement use fresh guarded helper workspaces named post53-pgmem and
post53-pgmem-control (8/4GiB budgets,12GiB free reserve). Put campaign.py/run.py
and analyze.py in the first evidence directory; invoke campaign.py with absolute
Python/script paths and a clean checkout of this measurement branch as argv[1].
It makes standalone clean clones for VCS-stamped builds. The published control
run.py uses that first workspace's clean harness/main binary and builds only a
new checked v0.6.0 dependency through an alternate modfile. Run each script via
experiment_workspace.py run; finalize/preserve/clean after all users stop.
Go1.27.3,macOS/libproc/sysctl and network access to the pinned pgmem/dependencies
are required. Build/acquisition are outside reported timing; no performance CI.
