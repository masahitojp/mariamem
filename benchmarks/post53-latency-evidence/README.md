# Post-#53 lightweight latency evidence

See [report](../post53-latency.md) for scope and conclusions. Summary derives only
from records with repetition>=0. Keep warmup records, not in the median. Inputs
retain exact commit/tag, guest/harness/binary hashes and VCS-clean build stamps.
The published recipe replaces only its local source path with argv[1]; executed
and published recipe hashes are explicitly distinct. It does not update any
original receipt on execution; run it only in a fresh disposable workspace.

Reproduce (compilation can take several minutes; measurement itself is bounded):
prepare an experiment workspace with4 GiB budget/8 GiB free reserve, place this
run.py in its evidence directory, then use experiment_workspace.py run with
absolute Python/script paths and a clean source checkout argument. The source
checkout needs the pinned v0.6.0 tag and candidate commit. `run.py` creates clean
standalone clones in temp so Go stamps the actual source. It requires only
Python's standard library, Go1.26.10 and macOS sysctl. No product code is edited.

Verify retained files and independently recalculate medians, read-only:

```sh
python3 - <<'PYCODE'
from pathlib import Path
import hashlib,json,statistics
p=Path('.')
for n,h in json.loads((p/'SHA256SUMS.json').read_text()).items():
    assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h,n
records=json.loads((p/'records.json').read_text())
summary=json.loads((p/'summary.json').read_text())
assert len(records)==48
for name,row in summary.items():
    case,mode=name.rsplit('-',1)
    med={}
    for label in ('baseline','candidate'):
        values=[r['seconds'] for r in records if r['case']==case and r['mode']==mode and r['label']==label and r['repetition']>=0]
        assert len(values)==3 and values==row['raw_seconds'][label]
        med[label]=statistics.median(values)
    assert med==row['median_seconds']
    assert 100*(med['candidate']/med['baseline']-1)==row['change_percent']
PYCODE
```
