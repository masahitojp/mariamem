"""Reconcile the reviewed semantic ledger with every fixed guest writer/read.

This checks coverage and source identity, not the truth of a semantic argument.
The manually reviewed target/protocol arguments live in targets.json/report.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OLD = ROOT / "docs/reviews/v050-access-paths-evidence"

GLOBALS = {
    24020809: "purge-enabled", 24020810: "purge-skipped", 24020811: "purge-active",
    15104498: "file-flush", 24021288: "encrypt-rotate", 15102238: "recovery-on",
    24051142: "load-abort", 24051920: "deadlock-request", 15138752: "ahi-enabled",
    15209600: "cleaner-idle", 15209756: "lru-scan", 15209757: "lru-warned",
    24088372: "cleaner-active", 24088732: "checkpoint", 24215400: "purge-count",
    24220996: "cache-warning",
}
OBJECTS = {
    4054: "guard", 16535: "pool-pending", 16537: "pool-pending",
    16684: "read-view", 17368: "recovery-page", 17388: "recovery-page",
    17405: "recovery-page", 17408: "recovery-page", 17410: "recovery-page",
    17412: "recovery-page", 17463: "file-corrupt", 17472: "file-extend",
    17770: "deadlock-victim", 17889: "ahi-block", 18090: "io-reserved",
    18114: "io-reserved", 18218: "recovery-page", 18221: "io-reserved",
    18497: "read-view", 18500: "read-view", 18511: "read-view",
    18531: "purge-enabled",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(fn, statement):
    hits = [name for addr, name in GLOBALS.items() if f"int32({addr})" in statement]
    if hits:
        assert len(hits) == 1
        return hits[0], "literal global address; source/use cross-reference"
    if fn in OBJECTS:
        return OBJECTS[fn], "object/value flow and source layout; not DWARF"
    if "AtomicStore32_16" in statement:
        assert fn in {17888, 18136, 18565}
        return "ahi-block", "buf_block +220 and source n_hash_helps"
    if fn in {17888, 17950}:
        for offset, target in ((68, "ahi-analysis"), (69, "ahi-potential"), (70, "ahi-success")):
            if f", int32({offset})," in statement:
                return target, "dict_index search_info byte and source/use cross-reference"
    if fn == 18241:
        if ", int32(1384)," in statement:
            return "read-view", "trx +1384 = embedded ReadView +40"
        if ", int32(192)," in statement:
            return "deadlock-victim", "trx +192; inlined reset, not read-view target"
    raise ValueError(f"unreviewed binding: Fn{fn}: {statement}")


# Every ordinary read in Fn88/93/130, keyed by the fixed generated source line.
# Each class has a consumer/revalidation argument in the report. No default.
READ_CLASSES = {
    88: {
        "futex-precheck": [402], "host-result-local": [415], "futex-timeout-recheck": [419],
    },
    93: {
        "immutable-mutex-type": [1001, 1025, 1058, 1066, 1088, 1366, 1430, 1712, 1852],
        "owner-test-before-cas": [1089, 1431, 1853],
        "agent-local-self-tid": [1092, 1093, 1434, 1435, 1730, 1731, 1856, 1857],
        "owner-local-robust-list": [1109, 1218, 1451, 1560, 1873, 1982],
        "waiter-robust-acquire-hint": [1121, 1245, 1286, 1463, 1587, 1628, 1885, 2009, 2050],
        "waiter-spin-hint": [1377, 1393],
        "waiter-cas-loop": [1743, 1806],
        "owner-local-recursion": [1153, 1166, 1495, 1508, 1917, 1930],
        "lock-spin-precheck": [1357, 1385, 1698],
        "agent-local-cancel": [1799],
    },
    130: {
        "immutable-mutex-type": [2294], "unlock-waiter-hint": [2296],
        "release-cas-loop": [2303, 2356, 2402],
        "agent-local-self-tid": [2330, 2331], "unlock-owner-check": [2332],
        "owner-local-robust-list": [2343, 2344, 2389, 2390],
        "owner-local-recursion": [2382],
    },
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    inventory = json.loads((OLD / "writer-inventory.json").read_text())
    graph = json.loads((OLD / "direct-call-graph.json").read_text())
    provenance = json.loads((ROOT / "internal/generatedgo/provenance.json").read_text())
    targets = json.loads((HERE / "targets.json").read_text())
    traces = json.loads((ROOT / "docs/reviews/v050-shared-impact-evidence/trace-receipts.json").read_text())
    files = {}

    def lines(relative):
        if relative not in files:
            path = ROOT / relative
            assert sha(path) == provenance["files_sha256"][relative.removeprefix("internal/generatedgo/")], relative
            files[relative] = path.read_text().splitlines()
        return files[relative]

    sites = []
    for f in inventory:
        source = lines(f["file"])
        for writer in f["writers"]:
            assert source[writer["line"] - 1].strip() == writer["statement"]
            target, confidence = binding(f["fn"], writer["statement"])
            assert target in targets, target
            sites.append({"fn": f["fn"], "primary_family": f["family"], "file": f["file"],
                          **writer, "target": target, "binding_basis": confidence,
                          "requested_bits": 16 if "32_16" in writer["helper"] else 8,
                          "effective_guest_operand_bits": 16 if "32_16" in writer["helper"] else 8,
                          "protocol": targets[target]["protocol"],
                          "prior_real_guest_observation": [key for key in ("targeted-default", "targeted-ahi")
                              if any(row["fn"] == f["fn"] and writer["line"] in row["executed_sites"]
                                     for row in traces[key]["executed_functions"])],
                          "observation_identity": "82f3c2bcef1518dadf5138a03e11dcfeb3db2de6 plus saved observer; same guest function, old widened helper; not new execution or simultaneity proof"})
    assert len(inventory) == 65 and len(sites) == 147
    assert set(targets) == {s["target"] for s in sites}, "target coverage differs"
    read_rows = []
    for fn, groups in READ_CLASSES.items():
        info = graph[str(fn)]
        source = lines(info["file"])
        start = info["line"] - 1
        end = next((j for j in range(start + 1, len(source)) if re.match(r"func Fn\d+\(", source[j])), len(source))
        actual = {n + 1 for n in range(start, end) if re.search(r"= .*\*\(\*(?:u?int\d+)\).*MemoryEA", source[n])}
        classified = {n for ns in groups.values() for n in ns}
        assert len(classified) == sum(map(len, groups.values())), "duplicate read"
        assert actual == classified, {"fn": fn, "missing": sorted(actual-classified), "extra": sorted(classified-actual)}
        for group, ns in groups.items():
            read_rows.extend({"fn": fn, "file": info["file"], "line": n, "class": group, "statement": source[n-1].strip()} for n in ns)
    # Literal global references include inlined join copies which a direct-call
    # graph alone misses. This slice is evidence, not a whole-program alias proof.
    thread_rows = []
    for relative in sorted({v["file"] for v in graph.values()}):
        fn = None
        for n, statement in enumerate(lines(relative), 1):
            match = re.match(r"func Fn(\d+)\(", statement)
            if match:
                fn = int(match[1])
            if "15243132" in statement:
                assert fn is not None
                thread_rows.append({"fn": fn, "line": n, "statement": statement.strip(),
                                    "file": relative, "symbol": graph[str(fn)]["symbol"]})
    result = {"writer_functions": len(inventory), "writer_sites": len(sites),
              "primary_families": len({f["family"] for f in inventory}), "targets": len(targets),
              "ordinary_read_statements": len(read_rows),
              "thread_list_literal_references": len(thread_rows),
              "thread_list_functions": sorted({r["fn"] for r in thread_rows}),
              "helpers": dict(Counter(s["helper"] for s in sites)),
              "sites_per_target": dict(sorted(Counter(s["target"] for s in sites).items())),
              "input_sha256": {p.name: sha(p) for p in (OLD / "writer-inventory.json", OLD / "direct-call-graph.json", HERE / "targets.json")},
              "generated_sha256": {name: sha(ROOT / name) for name in sorted(files)},
              "limit": "Mechanical reconciliation; semantic conclusions require the linked protocol arguments. Counts do not prove alias or lifetime correctness."}
    for name, data in (("thread-list-accesses.json", thread_rows), ("writer-ledger.json", sites), ("ordinary-reads.json", sorted(read_rows, key=lambda r:(r['fn'],r['line']))), ("coverage.json", result)):
        (args.output / name).write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
