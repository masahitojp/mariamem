"""Aggregate the driver's raw.jsonl into one JSON the website renders.

For every model the representative run is the one whose total is the
median, so the timeline is a real run, not an average of runs that never
happened together. Totals also carry min and max over all runs, and the
step sums (time spent in each kind of node, added over lanes) come from
the representative run.
"""
import json, platform, statistics, subprocess, sys
from collections import defaultdict

runs = defaultdict(list)
for line in open(sys.argv[1]):
    if line.strip():
        r = json.loads(line)
        runs[r["model"]].append(r)

def cmd(*a):
    try:
        return subprocess.check_output(a, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""

def orbstack_version():
    for line in cmd("orb", "version").splitlines():
        if line.lower().startswith("version:"):
            return "OrbStack " + line.split(":", 1)[1].split()[0]
    return ""

KINDS = ["boot", "import", "snapshot", "fork", "sample", "reset", "read", "write"]

models = {}
for model, rs in runs.items():
    rs = sorted(rs, key=lambda r: r["total_ms"])
    rep = rs[len(rs) // 2]
    steps = {k: 0.0 for k in KINDS}
    for s in rep["spans"]:
        steps[s["kind"]] += s["end_ms"] - s["start_ms"]
    lanes = sorted({s["lane"] for s in rep["spans"]}, key=lambda l: min(s["start_ms"] for s in rep["spans"] if s["lane"] == l))
    tests = [s for s in rep["spans"] if s["kind"] in ("read", "write")]
    models[model] = {
        "runs": len(rs),
        "parallel": rep["parallel"],
        "postgres": rep.get("version", ""),
        "total_ms": round(rep["total_ms"], 2),
        "total_min_ms": round(rs[0]["total_ms"], 2),
        "total_max_ms": round(rs[-1]["total_ms"], 2),
        "total_median_ms": round(statistics.median(r["total_ms"] for r in rs), 2),
        "boot_ms": round(rep["boot_ms"], 2),
        "process_ms": round(rep["process_ms"], 2),
        "tests": {"read": sum(1 for s in tests if s["kind"] == "read"), "write": sum(1 for s in tests if s["kind"] == "write")},
        "steps": {k: round(v, 2) for k, v in steps.items() if v},
        "lanes": lanes,
        "spans": [{**s, "start_ms": round(s["start_ms"], 2), "end_ms": round(s["end_ms"], 2)} for s in rep["spans"]],
    }

for k, m in models.items():
    print(f"{k:8s} total {m['total_ms']:8.1f} ms ({m['total_min_ms']:.0f}..{m['total_max_ms']:.0f}) steps: "
          + ", ".join(f"{s}={v:.0f}" for s, v in m["steps"].items()), file=sys.stderr)

print(json.dumps({
    "measured_at": cmd("date", "-u", "+%Y-%m-%d"),
    "machine": {
        "cpu": cmd("sysctl", "-n", "machdep.cpu.brand_string") or platform.processor(),
        "cores": cmd("sysctl", "-n", "hw.ncpu"),
        "memory_gb": round(int(cmd("sysctl", "-n", "hw.memsize") or 0) / 2**30),
        "os": f"{platform.system()} {platform.release()}",
        "go": cmd("go", "env", "GOVERSION"),
        "docker": cmd("docker", "version", "--format", "{{.Server.Version}}"),
        "docker_runtime": orbstack_version(),
        "devbox": cmd("devbox", "version").splitlines()[-1] if cmd("devbox", "version") else "",
    },
    "models": models,
}, indent=2))
