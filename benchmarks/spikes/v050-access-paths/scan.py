"""Pinned source/Generated-Go cross references for narrow writer path review.

This is a lexical inventory plus conservative direct call graph, not an alias
analysis, a race census, or an automatic safety verdict. It fails on input drift.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[3]
FAMILIES = {
    "guard": [4054],
    "pool": [16535, 16537],
    "view": [16684, 18241, 18497, 18500, 18511],
    "purge": [17151, 17161, 18168, 18180, 18231, 18595],
    "encryption": [17240, 17245, 17251, 18355],
    "file": [17218, 17221, 17463, 17472, 18572, 18580],
    "recovery": [17368, 17371, 17377, 17388, 17405, 17408, 17410, 17412],
    "load": [17437, 17440, 18570],
    "startup-shutdown": [17453, 17461, 18509, 18531],
    "deadlock": [17770, 17772, 17811, 17812],
    "ahi": [17877, 17880, 17888, 17889, 17950, 18136, 18566],
    "buffer-io": [17994, 18002, 18005, 18006, 18008, 18010, 18090,
                  18114, 18122, 18218, 18221, 18565],
    "checkpoint": [18022, 18080],
    "table-cache": [20878],
}
QUERIES = {
    "purge": r"\b(?:m_initialized|m_enabled|m_active|skipped_rseg|srv_init_purge_tasks|srv_shutdown_purge_tasks|srv_purge_shutdown|coordinator_startup|coordinator_shutdown)\b|purge_sys\.(?:create|close)",
    "view": r"\b(?:m_open|ReadView|TrxFactory|register_trx|deregister_trx)\b|read_view\.(?:close|open|append_to)|trx_t::free",
    "ahi": r"\b(?:hash_analysis|n_hash_potential|last_hash_succ|n_hash_helps|dict_mem_index_create|dict_mem_index_free|dict_index_remove_from_cache)\b|dict_index_t::clone",
    "pool": r"\bm_thread_creation_pending\b|thread_pool_generic::~|\bworker_end\b|m_cv_no_threads",
    "buffer": r"\b(?:try_LRU_scan|LRU_warned|page_cleaner_idle_flag|buf_page_cleaner_is_active|reserved)\b",
    "others": r"\b(?:srv_encrypt_rotate|being_processed|recovery_on|being_extended|is_corrupted|buf_load_abort_flag|srv_purge_thread_count_changed|tc_contention_warning_reported|was_chosen_as_deadlock_victim|need_checkpoint|need_unflushed_spaces)\b",
    "lifetime": r"\b(?:memset|memcpy|memmove)\b.*(?:this|index|block|trx)|new\s*\([^)]*(?:read_view|search_info)|\*index\s*=\s*\*this",
}
SUFFIXES = {".h", ".hh", ".hpp", ".c", ".cc", ".cpp", ".inl", ".inc"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(out, name, value):
    (out / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def verify_archive(archive, source, pin, overrides=None):
    assert digest(archive.read_bytes()) == pin["sha256"], "archive identity differs"
    count = 0
    covered = set()
    with tarfile.open(archive) as tar:
        for member in tar:
            if not member.isfile():
                continue
            relative = Path(*Path(member.name).parts[1:])
            if relative.suffix not in SUFFIXES:
                continue
            expected = (overrides or {}).get(relative.as_posix())
            expected = expected or digest(tar.extractfile(member).read())
            assert digest((source / relative).read_bytes()) == expected, relative
            covered.add(relative.as_posix())
            count += 1
    for relative, expected in (overrides or {}).items():
        if Path(relative).suffix in SUFFIXES:
            assert digest((source / relative).read_bytes()) == expected, relative
            covered.add(relative)
    actual = {f.relative_to(source).as_posix() for f in source.rglob("*")
              if f.is_file() and f.suffix in SUFFIXES}
    assert actual == covered, "unregistered source files"
    assert count > 100, "source inventory unexpectedly small"
    return count


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("mariadb-archive", "wasix-archive", "mariadb-source", "wasix-source", "cxa-source", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    pins = {x["name"]: x for x in json.loads((ROOT / "release/inputs.lock.json").read_text())["inputs"]}
    guest = json.loads((ROOT / "guest/input.json").read_text())
    overrides = {}
    for patch in guest["patches"]:
        assert digest((ROOT / patch["file"]).read_bytes()) == patch["sha256"]
        overrides.update(patch["after_sha256"])
    counts = {
        "mariadb": verify_archive(a.mariadb_archive, a.mariadb_source, pins["mariadb"], overrides),
        "wasix": verify_archive(a.wasix_archive, a.wasix_source, pins["wasix-libc"]),
    }
    old = json.loads((ROOT / "docs/reviews/v050-shared-impact-evidence/identities.json").read_text())
    for name in ("cxa_guard.cpp", "cxa_guard_impl.h"):
        assert digest((a.cxa_source / name).read_bytes()) == old["source_archives"][name]
    provenance = json.loads((ROOT / "internal/generatedgo/provenance.json").read_text())
    assert provenance["guest_sha256"] == old["wasm_sha256"]
    function_map = ROOT / "docs/reviews/v050-ad-integration-evidence/function-map.txt"
    assert digest(function_map.read_bytes()) == old["function_map_sha256"]
    names = {int(s.split(":", 1)[0]): s.split(":", 1)[1] for s in function_map.read_text().splitlines()}
    rows = json.loads((ROOT / "docs/reviews/v050-shared-impact-evidence/generated-sites.json").read_text())
    by_function = collections.defaultdict(list)
    for row in rows:
        by_function[row["fn"]].append(row)
    family = {fn: key for key, funcs in FAMILIES.items() for fn in funcs}
    assert len(family) == sum(map(len, FAMILIES.values())) == len(by_function) == 65
    assert set(family) == set(by_function), "writer scope changed"
    functions, callers, generated_hits, excerpts = {}, collections.defaultdict(set), [], []
    actual_writers = []
    extra = {65, 21692, 4053, 4054, 4055, 88, 89, 90, 93, 130, 92, 221,
             18228, 18231, 18180, 17461}
    for file in sorted((ROOT / "internal/generatedgo/code").glob("p*/*_pure.go")):
        relative = file.relative_to(ROOT).as_posix()
        raw = file.read_bytes()
        # Installation preserves all transpiled function files; verify receipt.
        assert digest(raw) == provenance["files_sha256"][relative.removeprefix("internal/generatedgo/")]
        lines = raw.decode().splitlines()
        starts = [(i, int(m[1])) for i, s in enumerate(lines)
                  if (m := re.match(r"func Fn(\d+)\(.*\{\s*$", s))]
        for (start, fn), (end, _) in zip(starts, starts[1:] + [(len(lines), 0)]):
            body = lines[start:end]
            direct = sorted(set(int(x) for x in re.findall(r"\bFn(\d+)\(", "\n".join(body[1:]))))
            functions[fn] = {"file": relative, "line": start + 1, "symbol": names[fn], "direct_callees": direct,
                             "indirect_calls": sum(bool(re.search(r"m\.T\d+\[.*\]\.\(func\(|CallIndirect", s)) for s in body)}
            for callee in direct:
                callers[callee].add(fn)
            if fn in by_function:
                for row in by_function[fn]:
                    assert row["file"] == relative and row["statement"] == lines[row["line"] - 1].strip()
            for k, line in enumerate(body):
                if re.search(r"base\.Atomic(?:Store|Rmw)\w*_(?:8|16)\w*\(", line):
                    actual_writers.append((fn, relative, start + k + 1, line.strip()))
                if fn in by_function and re.search(r"base\.Atomic(?:Load|Store|Rmw)\w*_(?:8|16)\w*\(", line):
                    generated_hits.append({"fn": fn, "file": relative, "line": start + k + 1, "statement": line.strip()})
            if fn in by_function or fn in extra:
                selected = set(range(len(body))) if len(body) < 200 else set()
                if not selected:
                    for k, line in enumerate(body):
                        if re.search(r"Atomic(?:Load|Store|Rmw)|Memory(?:Fill|Copy)|Fn(?:65|93|130|221|18531)\(|1520975|240208", line):
                            selected.update(range(max(0, k - 3), min(len(body), k + 4)))
                excerpts.append(f"Fn{fn} {names[fn]} {relative}:{start + 1}\n" +
                                "\n".join(f"{start + k + 1}: {body[k]}" for k in sorted(selected)))
    assert sorted(actual_writers) == sorted((r["fn"], r["file"], r["line"], r["statement"]) for r in rows)
    assert len(functions) == 21628, "defined function scope changed"
    inventory = []
    for fn in sorted(family):
        inventory.append({**functions[fn], "fn": fn, "family": family[fn], "writers": [{key: row[key] for key in ("line", "helper", "statement")} for row in by_function[fn]],
                          "direct_callers": sorted(callers[fn]),
                          "verdict": "Source/lifetime review required; graph is not an alias or safety proof"})
    save(out, "writer-inventory.json", inventory)
    save(out, "generated-accesses.json", generated_hits)
    save(out, "direct-call-graph.json", {str(fn): info for fn, info in functions.items()})
    (out / "generated-excerpts.txt").write_text("\n\n".join(excerpts) + "\n")
    hits, source_hashes = [], {}
    compiled = {key: re.compile(pattern) for key, pattern in QUERIES.items()}
    for file in sorted(a.mariadb_source.rglob("*")):
        if file.suffix not in SUFFIXES or not file.is_file():
            continue
        rel = file.relative_to(a.mariadb_source).as_posix()
        if not rel.startswith(("storage/innobase/", "tpool/", "sql/table_cache", "include/my_atomic_wrapper")):
            continue
        raw = file.read_bytes()
        lines = raw.decode(errors="replace").splitlines()
        for i, line in enumerate(lines):
            for key, pattern in compiled.items():
                if pattern.search(line):
                    source_hashes[rel] = digest(raw)
                    hits.append({"query": key, "file": rel, "line": i + 1, "text": line.strip(),
                                 "context": lines[max(0, i - 2):i + 3]})
    save(out, "source-references.json", hits)
    save(out, "identity.json", {"guest_sha256": old["wasm_sha256"], "function_map_sha256": old["function_map_sha256"],
                               "canonical_provenance_sha256": digest((ROOT / "internal/generatedgo/provenance.json").read_bytes()),
                               "source_archives": {k: pins[k] for k in ("mariadb", "wasix-libc")},
                               "source_files_verified": counts, "cxa_files_sha256": {n: old["source_archives"][n] for n in ("cxa_guard.cpp", "cxa_guard_impl.h")},
                               "selected_source_files_sha256": source_hashes,
                               "counts": {"writer_functions": len(inventory), "writer_sites": len(rows), "source_references": len(hits)},
                               "limit": "Lexical references and direct calls are complete only for the named source tokens/scope. Raw-pointer aliases, implicit constructors and indirect calls need human analysis."})
    print("PASS: pinned source bytes, 65 writer functions / 147 sites, lexical references and direct call graph")


if __name__ == "__main__":
    main()
