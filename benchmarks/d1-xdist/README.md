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
