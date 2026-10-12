"""Save selected compact evidence with explicit raw/saved hash distinction."""
import argparse
import hashlib
import json
from pathlib import Path

FILES = ["source.json", "source-inputs.json", "converter-patches.json", "source-verification.json",
         "source-anchors.json", "writer-ledger.json", "ordinary-reads.json", "coverage.json",
         "thread-list-accesses.json", "indirect-calls.json", "callback-data.json", "fence-results.json",
         "timing.json", "checks.json"]
PROBE = ["probe-results.json", "protocol-heap.txt", "protocol-heap-race.txt", "protocol-mmap.txt",
         "protocol-mmap-race.txt", "timeout-boundary.txt", "thread-boundary.txt", "probe-vet.txt",
         "probe-compile.txt", "mutex-arm64-disassembly.txt"]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    workspace = a.workspace.resolve()
    a.output.mkdir(parents=True, exist_ok=True)
    manifest = {}
    pairs = [(name, name) for name in FILES] + [("final-probe-v2/"+name, name) for name in PROBE]
    for relative, name in pairs:
        raw = (workspace/"evidence"/relative).read_bytes()
        saved = raw.replace(str(workspace).encode(), b"<workspace>")
        if name.endswith(".txt"):
            saved = b"\n".join(line.rstrip() for line in saved.split(b"\n"))
        (a.output/name).write_bytes(saved)
        manifest[name] = {"raw_source":relative,"raw_sha256":sha(raw),"saved_sha256":sha(saved),
                          "raw_bytes":len(raw),"saved_bytes":len(saved),"normalized":raw != saved}
    (a.output/"manifest.json").write_text(json.dumps({"normalization":"replace absolute owned-workspace prefix with <workspace> and strip trailing whitespace in text logs; nested receipt hashes remain raw artifact/log hashes", "files":manifest},indent=2)+"\n")
    print(f"Saved {len(manifest)} compact evidence files; raw and normalized hashes kept separately")


if __name__ == "__main__":
    main()
