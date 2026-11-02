# D1 xdist worker-local feasibility spike

Base source_commit: f09d5167172f091ccc0b20f78b817fe870d3cadf.
Question: can local pytest-xdist workers each own an independent D1 host and
baseline, without sharing SDK handles or changing the engine/Django runner?
This informs whether to productize that one mode; it is not production support.

Initial scope: authored orders app, fixed Django5.2.8 / pytest-django4.12.0 /
pytest9.0.2 / xdist3.8.0, published0.6.0 host reuse, local macOS arm64.
Observe per-worker DB name/host identity, preparation and class setup counts,
committed/non-model state restoration, real overlap barriers and final host PIDs.
Success needs ordinary/loadscope/reverse/expected-failure runs plus preparation
failure refusing that worker's bodies and a no-restore control detecting damage.
No timing speedup, resource census, worker-kill recovery, remote workers, Django
--parallel or both-OS/installed-wheel support claim.

Budget: initial2h active, at most30min tooling, no heavy CI. An inconclusive
result must name the concrete obstacle and cost; do not expand the framework.
Only experiment/d1-xdist changes the xdist refusal; main stays unchanged.

## Reproduce

Use the pinned published0.6.0 host, not a freshly stamped unrelated binary.
The collector checks its source revision. After checking out the executed spike:

```sh
python3 scripts/git_identity.py inspect HEAD
python3 -m venv .venv
.venv/bin/python -m pip install -r tests/django_lifecycle/requirements.txt pytest-xdist==3.8.0 execnet==2.1.2
.venv/bin/python benchmarks/d1-xdist/run.py --host /path/to/v060/mariamem-host --output /tmp/d1-xdist-case --workers 2 --mode healthy --dist load
```

Repeat with (mode, workers, scheduler): healthy/2/load, healthy/4/load,
reverse/2/load, body-failure/2/load, prepare-failure/2/load,
no-restore/2/load, healthy/2/loadscope. Each output path must be new.
`no-restore` deliberately breaks test-child restoration and must detect failures;
the parent assessment recognizes that negative control, while stdout/JUnit keep
original failures. The fixture barriers require every requested worker to
receive DB tests; these fixed cases do so. They are not a generic idle-worker
scheduler test. There is no production promise of arbitrary worker counts.
