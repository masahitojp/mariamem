#!/usr/bin/env python3
"""One MariaDB template plus independent forks versus freshly seeded containers."""
from _common import backends, one, options, record, run, template


def benchmark(args, report):
    for backend in backends(args):
        for phase, count in (("warmup", args.warmup), ("measurement", args.runs)):
            if not count:
                continue
            with template(backend, args, report, phase) as saved:
                samples = []
                for index in range(count):
                    result = one(backend, args, snapshot=saved, seeded=True)
                    samples.append(result)
                    record(report, backend, phase, index, result)
                prep = sum(p["seconds"] for p in report["preparations"]
                           if p["backend"] == backend and p["phase"] == phase)
                total = prep + sum(s["ready_seconds"] for s in samples)
                report.setdefault("amortized", []).append({"backend": backend, "phase": phase,
                    "preparation_seconds": prep, "prep_plus_ready_seconds": total,
                    "seconds_per_db_including_preparation": total / count,
                    "cleanup_seconds": sum(s["cleanup_seconds"] for s in samples)})
                print(f"{backend} {phase}: prep={prep:.3f}s prep+ready={total:.3f}s "
                      f"amortized={total/count:.3f}s/DB (cleanup separate)")


if __name__ == "__main__":
    run(options(__doc__, seeded=True), benchmark, "seeded_database")
