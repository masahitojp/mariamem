"""Keep compact, path-independent receipts from the disposable study workspace."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


parser = argparse.ArgumentParser()
parser.add_argument("task", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
task = args.task.resolve()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
temp = task / "temp"

for name in ("scan-summary.json", "wasm-sites.json", "generated-sites.json"):
    shutil.copyfile(temp / "scan-final" / name, out / name)
for name in ("candidate-wasm-calls.json", "wasm-go-comparison.json",
             "static-ordinary-global-constant-ea.json"):
    shutil.copyfile(task / "evidence" / name, out / name)

identities = json.loads((task / "evidence" / "identities.json").read_text())
identities["binaries"]["observed-targeted-host"] = {
    "sha256": sha(temp / "observed-targeted-host"),
    "vcs_stamp": "-buildvcs=false; exact modified-file manifest and observer hash below",
}
identities["instrumentation_v1_sha256"] = sha(task / "evidence" / "instrumentation-v1.json")
identities["instrumentation_v2_sha256"] = sha(temp / "instrumentation.json")
identities["observer_v2_sha256"] = sha(task / "worktree" / "benchmarks" / "spikes" / "v050-shared-impact" / "observer.go.txt")
identities["raw_event_sha256"] = {
    name: sha(temp / name / "events.json")
    for name in ("targeted-default", "targeted-ahi")
}
write(out / "identities.json", identities)

manifest = json.loads((temp / "instrumentation.json").read_text())
write(out / "instrumentation-v2.json", manifest)

results = {}
for name in ("control-final-default-retry", "targeted-default",
             "control-ahi-retry", "targeted-ahi"):
    r = json.loads((temp / name / "results.json").read_text())
    results[name] = {
        "result": r["result"],
        "observe": r["observe"],
        "version": r["version"],
        "ahi_initial": r["ahi_initial"],
        "ahi_active": r["ahi_active"],
        "startup_seconds": r["startup_seconds"],
        "close_seconds": r["close_seconds"],
        "cases": r["cases"],
    }
write(out / "scenario-results.json", results)

traces = {}
for name in ("targeted-default", "targeted-ahi"):
    s = json.loads((temp / name / "summary.json").read_text())
    events = json.loads((temp / name / "events.json").read_text())
    # Raw addresses and Module pointers are run-local. Retain selected examples,
    # plus the complete purge lifecycle timeline, but not huge unsorted row maps.
    sample = []
    seen = set()
    for ex in s["examples"]:
        word = ex["word"]
        fn = ex["writer"]["key"]["fn"]
        other_fn = ex["other"]["key"]["fn"]
        if word != 24020808 and fn not in (17888, 17950, 18136, 18010):
            continue
        key = (word, fn, other_fn, ex["relation"])
        if key in seen:
            continue
        seen.add(key)
        sample.append(ex)
        if len(sample) == 30:
            break
    traces[name] = {
        "raw_sha256": sha(temp / name / "events.json"),
        "raw_distinct_rows": len(events["rows"]),
        "dropped": s["dropped"],
        "cas_retries": s["cas_retries"],
        "executed_functions": s["executed_functions"],
        "cross_actor_ordinary_address_pair_combinations": s["cross_actor_ordinary_pair_count"],
        "cross_actor_extra_atomic_address_pair_combinations": s["cross_actor_extra_atomic_pair_count"],
        "pair_definition": s["interpretation"],
        "selected_address_pair_examples": sample,
        "purge_timeline": events["purge_timeline"],
    }
write(out / "trace-receipts.json", traces)

print("PASS: compact evidence exported", len(traces), "runs")
