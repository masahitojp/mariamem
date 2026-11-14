"""Read-only compact receipt verification; no temp/build dependencies."""
from pathlib import Path
import csv
import hashlib
import json
import math
import statistics

ROOT = Path(__file__).resolve().parent

def read(name):
    return json.loads((ROOT / name).read_text())

for name, expected in read("SHA256SUMS.json").items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
rows = list(csv.DictReader((ROOT / "child-close.csv").open()))
runs = read("runs.json")
assert len(runs) == 24 and len(rows) == 960
for run in runs:
    assert run["exit_code"] == 0 and run["success"] and run["cleanup"]
    assert run["scratch_empty"] and run["oracles"] == run["children"]
    stats = run["cleanup_stats"]
    for key in ("active_mappings", "active_rw_bytes", "active_reserved_bytes", "release_failures"):
        assert stats[key] == 0
    assert stats["creates"] == stats["releases"]
summary = {}
for arm in ("before", "after"):
    selected = [r for r in rows if r["arm"] == arm]
    assert len(selected) == 480
    assert {(int(r["pair"]), int(r["child"])) for r in selected} == {(p, c) for p in range(10) for c in range(48)}
    assert all(r["oracle"] == r["cleanup"] == "True" for r in selected)
    vals = sorted(float(r["close_ms"]) for r in selected)
    primary = [r for r in runs if r["arm"] == arm and r["kind"] == "primary"]
    assert len(primary) == 10 and all(not r["trace_files"] for r in primary)
    summary[arm] = dict(primary_processes=10, children=len(vals), close_p50_ms=statistics.median(vals),
                        close_p95_ms=vals[math.ceil(.95 * len(vals))-1], close_max_ms=max(vals),
                        close_over_2000ms=sum(v > 2000 for v in vals))
assert summary == read("summary.json")
controls = read("observer-controls.json")
assert {c["arm"] for c in controls} == {"before", "after"}
for control in controls:
    meta = control["metadata"]
    assert meta["control"] and not meta["stack_truncated"] and 0 < meta["stack_bytes"] <= 2 * 1024 * 1024
    assert "observeClose" in (ROOT / control["excerpt_file"]).read_text()
completion = read("completion.json")
assert completion["result"] == "INCONCLUSIVE_NO_REPRODUCTION"
assert completion["primary_processes"] == completion["max_primary_processes"] == 20
assert completion["retries"] == 0 and not completion["product_changes"]
assert read("inputs.json")["harness_source_commit"] == completion["harness_source_commit"]
print("Compact evidence verified: 20 primary processes / 960 children; no reproduction.")
