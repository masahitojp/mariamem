"""Replay the source census; --check never modifies retained evidence."""

import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from git_identity import require_commit


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    plan = json.loads((HERE / "plan.json").read_text())
    require_commit(REPO, plan["source_commit"])
    upstream = args.upstream.resolve()
    assert upstream.name == "server-" + plan["mariadb_source_commit"]
    census = subprocess.check_output(
        ["rg", "--no-ignore", "--hidden", "-n", "--no-heading", "--color", "never",
         r"sys_timer_info|\bmy_timer_init\(", "."], cwd=upstream, text=True
    )
    census = "\n".join(sorted(line.removeprefix("./") for line in census.splitlines())) + "\n"
    rows = []
    address = re.compile(r"\b26639\d{3}\b")
    function = re.compile(r"^func (Fn\d+)\(")
    files = sorted((REPO / "internal/generatedgo/code").glob("p*/*_pure.go"))
    for path in files:
        current = None
        with path.open() as stream:
            for number, line in enumerate(stream, 1):
                match = function.match(line)
                if match:
                    current = match[1]
                if any(26639680 <= int(value) < 26639840 for value in address.findall(line)):
                    rows.append(dict(path=str(path.relative_to(REPO)), line=number,
                                     function=current, text=line.strip()))
    outside = [row for row in rows if row["function"] != "Fn5573"]
    assert len(outside) == 13
    assert all("base.MemoryEA(m, 26639696, 0, 8)" in row["text"] for row in outside)
    selected = [
        "mysys/my_rdtsc.c", "include/my_rdtsc.h", "sql/sql_analyze_stmt.h",
        "libmysqld/lib_sql.cc", "mysys/charset.c", "mysys/charset-def.c",
        "mysys/array.c", "mysys/hash.c", "mysys/my_once.c", "strings/ctype.c",
        "strings/ctype-uca.c", "strings/ctype-uca1400.c", "strings/ctype-uca1400.h",
        "strings/ctype-uca.h", "strings/ctype-uca0900.c",
        "storage/perfschema/pfs_timer.cc", "storage/perfschema/table_performance_timers.cc",
    ]
    hashes = {"upstream/" + name: hashlib.sha256((upstream / name).read_bytes()).hexdigest()
              for name in selected}
    for path in files + [REPO / "guest/source.patch", REPO / "guest/patches/common-portability.patch"]:
        relative = str(path.relative_to(REPO))
        data = path.read_bytes()
        expected = subprocess.check_output(["git", "show", plan["source_commit"] + ":" + relative], cwd=REPO)
        assert data == expected, relative + " differs from product source"
        hashes["product/" + relative] = hashlib.sha256(data).hexdigest()
    summary = dict(
        source_commit=plan["source_commit"], mariadb_source_commit=plan["mariadb_source_commit"],
        census_lines=len(census.splitlines()),
        generated_literal_reference_counts=dict(sorted(collections.Counter(row["function"] for row in rows).items())),
        generated_non_initializer_references=outside,
        limitation="Text and literal-address census; not an alias/pointer dataflow proof or SQL runtime test.",
        sha256=hashes,
    )
    outputs = {"timer-census.txt": census, "source-audit.json": json.dumps(summary, indent=2) + "\n"}
    for name, content in outputs.items():
        target = HERE / "results" / name
        if args.check:
            assert target.read_text() == content, name
        else:
            target.parent.mkdir(exist_ok=True)
            target.write_text(content)
    print("Source census " + ("matches retained evidence" if args.check else "saved"))


if __name__ == "__main__":
    main()
