#!/bin/bash
# Measure pgmem next to docker run, testcontainers-go and devbox.
#   RUNS=5 MEM_RUNS=3 ./run.sh -> results/raw.jsonl, results/sizes.json, results/summary.json
#   SKIP_TIMING=1 ./run.sh     -> keep raw.jsonl's timing samples, redo only the memory pass
# Requires OrbStack with postgres:18-alpine pulled, and devbox.
#
# Two passes. The timing pass leaves the Docker VM running between runs, as
# a developer's machine would. The memory pass restarts OrbStack before
# each docker and testcontainers run. It records container stats plus
# benchmark-process growth as the comparable service footprint, and records
# the VM's net change and absolute footprint separately for host context.
# The memory pass refuses to restart OrbStack while other containers run.
set -euo pipefail
cd "$(dirname "$0")"
RUNS=${RUNS:-5}
MEM_RUNS=${MEM_RUNS:-3}
SKIP_TIMING=${SKIP_TIMING:-0}
IMAGE=${IMAGE:-postgres:18-alpine}
OUT=results
mkdir -p "$OUT" bin
go build -o bin/alternatives .
go build -C ../.. -ldflags='-s -w' -o bench/alternatives/bin/pgmem ./cmd/pgmem
docker pull -q "$IMAGE" >/dev/null
devbox install -q -c devbox >/dev/null 2>&1

if [ "$SKIP_TIMING" = 1 ]; then
  # drop earlier memory-pass samples, keep the timing pass
  grep -v '"fresh_vm": *true' "$OUT/raw.jsonl" > "$OUT/raw.tmp" || true
  mv "$OUT/raw.tmp" "$OUT/raw.jsonl"
  RUNS=0
else
  : > "$OUT/raw.jsonl"
fi
for ((i = 1; i <= RUNS; i++)); do
  for t in pgmem docker testcontainers devbox; do
    echo "run $i $t" >&2
    bin/alternatives -target "$t" -image "$IMAGE" >> "$OUT/raw.jsonl"
  done
  # the standalone binary that the Python, Java and Node.js wrappers spawn
  python3 - bin/pgmem >> "$OUT/raw.jsonl" <<'PY'
import json, os, subprocess, sys, tempfile, time
t0 = time.perf_counter()
p = subprocess.Popen([sys.argv[1], "-database", "app"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
p.stdout.readline()
ms = (time.perf_counter() - t0) * 1000
rss = int(subprocess.check_output(["ps", "-o", "rss=", "-p", str(p.pid)]).strip()) / 1024
with tempfile.TemporaryDirectory() as d:
    out = os.path.join(d, "fp.json")
    subprocess.run(["/usr/bin/footprint", "-f", "bytes", "--noCategories", "-j", out, str(p.pid)], capture_output=True)
    fp = json.load(open(out))["processes"][0]["auxiliary"]["phys_footprint"] / 2**20
p.stdin.close(); p.wait(timeout=10)
print(json.dumps({"target": "binary", "startup_ms": ms, "mem_idle_mb": fp, "rss_idle_mb": rss}))
PY
done

for ((i = 1; i <= MEM_RUNS; i++)); do
  for t in docker testcontainers; do
    echo "memory run $i $t (restarts OrbStack)" >&2
    bin/alternatives -target "$t" -image "$IMAGE" -fresh-vm >> "$OUT/raw.jsonl"
  done
done

if [ "$SKIP_TIMING" != 1 ]; then
  ./sizes.sh "$IMAGE" > "$OUT/sizes.tmp.json"
  mv "$OUT/sizes.tmp.json" "$OUT/sizes.json"
fi
python3 summarize.py "$OUT/raw.jsonl" "$OUT/sizes.json" > "$OUT/summary.json"
cp "$OUT/summary.json" ../../website/src/data/benchmarks.json
cat "$OUT/summary.json"
