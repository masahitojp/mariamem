"""Reduce compact comparison cells; keep startup noise visible."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--go", type=Path, required=True)
    p.add_argument("--imports", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    rows = []
    for boundary, folder in (("go", a.go), ("import", a.imports)):
        for size in (0, 10, 100):
            for label in ("baseline", "candidate"):
                docs = [json.loads(f.read_text()) for f in sorted(folder.glob(f"{boundary}-{size}-*-{label}.json"))]
                assert len(docs) == 3, (boundary, size, label, len(docs))
                ready = [o["seconds"] * 1000 for d in docs for o in d["operations"] if o["name"].startswith("fork_ready")]
                def med_total(predicate, field="seconds"):
                    return statistics.median(sum(o[field] for o in d["operations"] if predicate(o["name"])) for d in docs)
                is_loop = lambda n: n.startswith(("fork_ready", "point_use", "count_use", "point_and_count", "child_close"))
                is_preparation = lambda n: n in ("prepare_start", "prepare_setup", "snapshot", "import")
                is_first = lambda n: is_preparation(n) or (is_loop(n) and n.endswith("_00")) or n == "snapshot_close"
                row = dict(boundary=boundary, payload_mib=size, label=label, trials=len(docs), fork_samples=len(ready),
                           ready_p50_ms=statistics.median(ready), ready_p95_ms=sorted(ready)[math.ceil(len(ready)*.95)-1],
                           ready_cpu_p50_ms=1000*statistics.median([o["cpu_seconds"] for d in docs for o in d["operations"] if o["name"].startswith("fork_ready")]),
                           preparation_s=med_total(is_preparation), snapshot_or_import_ms=1000*med_total(lambda n:n in ("snapshot","import")),
                           fresh_start_ms=1000*med_total(lambda n:n=="prepare_start"),
                           fork_loop_s=med_total(is_loop), suite_n16_s=statistics.median(d["suite_operation_seconds"] for d in docs),
                           suite_n1_prefix_s=med_total(is_first), suite_cpu_s=med_total(lambda n:True,"cpu_seconds"))
                for key in ("fds_snapshot", "fds_after", "prepared_files", "prepared_bytes", "owned_fds"):
                    row[key] = docs[0].get(key, "")
                rows.append(row)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
    with (a.out / "summary.csv").open("w", newline="") as output:
        w = csv.DictWriter(output, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
