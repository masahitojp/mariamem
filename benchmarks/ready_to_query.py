#!/usr/bin/env python3
"""Fresh DB start through the first successful SELECT 1."""
from _common import backends, one, options, record, run


def benchmark(args, report):
    for backend in backends(args):
        for phase, count in (("warmup", args.warmup), ("measurement", args.runs)):
            for index in range(count):
                record(report, backend, phase, index, one(backend, args))


if __name__ == "__main__":
    run(options(__doc__), benchmark, "ready_to_query")
