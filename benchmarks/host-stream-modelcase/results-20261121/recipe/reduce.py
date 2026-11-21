"""Reduce preserved observations without requiring the experiment workspace."""
import csv
import gzip
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

out = Path(sys.argv[1])
records = [json.loads(gzip.decompress(f.read_bytes())) for f in sorted((out/"runs").glob("*.json.gz"))]
assert Counter(r["role"] for r in records) == dict(main=36, frames=8, warm=6, semantics=3)
median = statistics.median
mib = 1024**2
def save(name, value):
    (out/name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")

def csvfile(name, rows):
    with (out/name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

rows = []
phase_rows = []
peak_rows = []
stage_rows = []
for r in records:
    if r["role"] != "main":
        continue
    base = {k:r[k] for k in ("p", "block", "arm", "position")}
    tr = r["trace"]
    if r["p"] == 1:
        # Parent cleanup_drain is nested inside final Close. The other
        # selected spans are disjoint in serial mode.
        previous_end = 0
        stages = Counter()
        for span in sorted(tr["spans"], key=lambda s:s["start_ms"]):
            if span["kind"] == "cleanup":
                continue
            assert span["start_ms"] >= previous_end, span
            previous_end = span["end_ms"]
            stages[span["kind"]] += span["end_ms"] - span["start_ms"]
        stages["unassigned"] = tr["elapsed_ms"] - sum(stages.values())
        stage_rows.append({**base, **{k:round(stages[k],3) for k in sorted(stages)}})
    origin = int(tr["meta"]["origin_ns"])
    rss = [((ns - origin)/1e6, n/mib) for ns, n in r["rss"]]
    row = dict(**base, suite_ms=tr["elapsed_ms"], process_ms=r["process_ms"],
               cpu_ms=r["user_ms"]+r["system_ms"], peak_mib=r["peak_bytes"]/mib)
    rows.append(row)
    ms, resident = max(rss, key=lambda sample:sample[1])
    active = sorted({s["kind"] for s in tr["spans"] if s["start_ms"] <= ms <= s["end_ms"]})
    stage = ",".join(active) or ("after suite" if ms > tr["elapsed_ms"] else "between spans")
    peak_rows.append(dict(**base, sampled_peak_ms=ms, sampled_peak_mib=resident,
                          observed_stage=stage))
    for group, kinds in {"import":["import"], "snapshot":["snapshot"], "fork":["fork"],
                         "sample":["sample"], "sql":["read","write"], "close":["close"],
                         "final_close":["close"]}.items():
        spans = [s for s in tr["spans"] if s["kind"] in kinds
                 and (group != "final_close" or s["lane"] == "final")]
        values = [n for ms, n in rss if any(s["start_ms"] <= ms <= s["end_ms"] for s in spans)]
        phase_rows.append(dict(**base, phase=group, sample_count=len(values),
                               max_mib=max(values) if values else ""))
csvfile("runs.csv", rows)
csvfile("phase-rss.csv", phase_rows)
csvfile("sampled-peaks.csv", peak_rows)
csvfile("serial-stages.csv", stage_rows)
summary = {}
pairs = []
phases = {}
frame_report = {}
for p in (1, 8):
    group = [r for r in rows if r["p"] == p]
    metrics = ["suite_ms", "process_ms", "cpu_ms", "peak_mib"]
    indexed = {(r["arm"], r["block"]): r for r in group}
    assert len(indexed) == 18
    for arm in ("os","both","pg"):
        summary[f"p{p}-{arm}"] = {k:median(x[k] for x in group if x["arm"] == arm) for k in metrics}
        for key in {r["phase"] for r in phase_rows}:
            values = [r["max_mib"] for r in phase_rows if r["p"] == p and r["arm"] == arm
                      and r["phase"] == key and r["max_mib"] != ""]
            phases[f"p{p}-{arm}-{key}"] = dict(observed=len(values), median_max_mib=median(values) if values else None)
    for i in range(1,7):
        a, b = indexed["os", i], indexed["both", i]
        pairs.append(dict(p=p,block=i,**{k:100*(b[k]/a[k]-1) for k in metrics}))
    summary[f"p{p}-paired"] = {
        k:dict(change_pct=median(r[k] for r in pairs if r["p"] == p),
               lower=sum(r[k]<0 for r in pairs if r["p"] == p),
               min_pct=min(r[k] for r in pairs if r["p"] == p),
               max_pct=max(r[k] for r in pairs if r["p"] == p)) for k in metrics}
    for arm in ("os","both"):
        diag = [r for r in records if r["role"]=="frames" and r["p"]==p and r["arm"]==arm]
        counts = Counter()
        for r in diag:
            counts.update({int(n):c for n,c in r["frames"].items()})
        total = sum(counts.values())
        size = sum(n*c for n,c in counts.items())
        def quantile(q):
            cum = 0
            for n,c in sorted(counts.items()):
                cum += c
                if cum >= math.ceil(q*total):
                    return n
        bins = []
        lo = 0
        for hi in (1024,4096,16384,65536,262144,2**32):
            vals = [(n,c) for n,c in counts.items() if lo<n<=hi]
            bins.append(dict(upper_bytes=hi, count=sum(c for n,c in vals), bytes=sum(n*c for n,c in vals)))
            lo = hi
        frame_report[f"p{p}-{arm}"] = dict(runs=len(diag),count=total,bytes=size,
            p50=quantile(.5),p99=quantile(.99),max=max(counts),bins=bins)
csvfile("paired-change-pct.csv", pairs)
save("summary.json", summary)
save("rss-summary.json", phases)
save("frame-summary.json", frame_report)
