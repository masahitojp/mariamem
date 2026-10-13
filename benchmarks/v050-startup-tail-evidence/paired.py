#!/usr/bin/env python3
"""Balanced v0.5.0 Fresh startup comparison, 60 blocks x 3 arms."""
import hashlib
import itertools
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure


EXPECTED = {
    "ownedprepared": "528e8aa0e28b563d960e3a472d6e117617972ea58178dcee1411e28ba6aca244",
    "ownedprepared-spike": "de75d6bce5734cc9c3544d23810662763d8d6a6af141b4a6327157bb171b412d",
}
for filename, expected in EXPECTED.items():
    actual = hashlib.sha256((measure.root / filename).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"binary identity changed: {filename} {actual}")

arms = [
    ("serial-10mib", False),
    ("parallel-10mib", False),
    ("parallel-10mib", True),
]
permutations = list(itertools.permutations(arms))
destination = measure.root.parent / "evidence" / "paired-10mib.jsonl"
if destination.exists():
    raise SystemExit(f"refusing to overwrite existing evidence: {destination}")

with destination.open("w") as out:
    for block in range(60):
        for case, traced in permutations[block % len(permutations)]:
            started = datetime.now(timezone.utc).isoformat()
            record = measure.run(case, block, traced)
            record["block"] = block
            record["started_utc"] = started
            out.write(json.dumps(record, separators=(",", ":")) + "\n")
            out.flush()
            print(block, case, "trace" if traced else "plain",
                  round(record["wall_seconds"], 3),
                  round(max(record["ready_seconds"]), 3), flush=True)
