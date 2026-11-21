"""Verify identities, workload coverage, sampling, run order and response histograms."""
import gzip
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

out = Path(sys.argv[1])
def read(path):
    return json.loads((out/path).read_text())

assert read("mariamem-source.json")["source_commit"] == "5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c"
assert read("pgmem-source.json")["source_commit"] == "a61005d37d01e6671f814fe8ca828222e8147df4"
assert read("maria-binary.json")["sha256"] != read("frames-binary.json")["sha256"]
records = [json.loads(gzip.decompress(f.read_bytes())) for f in (out/"runs").glob("*.json.gz")]
assert Counter(r["role"] for r in records) == dict(main=36, frames=8, warm=6, semantics=3)
coverage = None
for r in records:
    tr = r["trace"]
    assert r["exit"] == 0 and tr["meta"]["model"] == ("pgmem" if r["arm"]=="pg" else "mariamem")
    assert r["user_ms"] > 0 and r["system_ms"] > 0 and r["peak_bytes"] > 0
    assert 0 < tr["elapsed_ms"] < r["process_ms"]
    obs = r["rss"]
    assert all(a[0] < b[0] for a,b in zip(obs, obs[1:])) and len(obs) > 10
    spans = tr["spans"]
    assert max(s["end_ms"] for s in spans) <= tr["elapsed_ms"]
    assert sum(s["lane"]=="final" and s["kind"]=="close" for s in spans) == 1
    if r["role"] != "semantics":
        covered = Counter((s["lane"],s["kind"]) for s in spans if s["kind"] in ("read","write","fork","sample","close"))
        if coverage is None:
            coverage = covered
        assert covered == coverage
        assert Counter(s["kind"] for s in spans)["sample"] == 21
        w = {s["lane"] for s in spans if s["kind"]=="write"}
        assert len(w) == 20 and sum(s["kind"]=="read" for s in spans)==50
        for kind in ("fork","close","sample"):
            assert w <= {s["lane"] for s in spans if s["kind"]==kind}
    assert ("frames" in r) == (r["role"]=="frames")

for p in (1,8):
    orders = []
    for block in range(1,7):
        group = sorted((r for r in records if (r["p"],r["role"],r["block"]) == (p,"main",block)),
                       key=lambda r:r["position"])
        orders.append(tuple(r["arm"] for r in group))
    assert set(orders) == set(itertools.permutations(("os","both","pg")))
    for arm in ("os","both"):
        frames = [r["frames"] for r in records if (r["role"],r["p"],r["arm"]) == ("frames",p,arm)]
        assert len(frames)==2
        summary = read("frame-summary.json")[f"p{p}-{arm}"]
        assert summary["count"] == sum(sum(hist.values()) for hist in frames)
        assert summary["bytes"] == sum(int(n)*v for hist in frames for n,v in hist.items())
print("PASS: identities, 53 processes, 36 measured suites, exact case/fork/load/close coverage, six orders per P, RSS series and independent frame counts")
