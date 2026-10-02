#!/usr/bin/env python3
"""Prepare the same SQL smoke consumer for the unmodified public pgmem module."""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE = "github.com/shibukawa/pgmem"
VERSION = "v1.18.1"
p = argparse.ArgumentParser()
p.add_argument("--work", type=Path, required=True)
a = p.parse_args()
work = a.work.resolve()
if not work.is_relative_to(ROOT / "build") or work == ROOT / "build":
    raise ValueError("use an isolated ignored build/ child")
if (work / "fixtures.json").exists():
    raise ValueError("use a fresh consumer fixture")
source = work / "mod-cache" / (MODULE + "@" + VERSION)
archive = work / "mod-cache/cache/download" / MODULE / "@v" / (VERSION + ".zip")
consumer = Path(tempfile.mkdtemp(prefix="pgmem-direct-consumer-"))
text = (Path(__file__).parent / "consumer.go.txt").read_text()
text = text.replace('"github.com/go-sql-driver/mysql"', '"github.com/jackc/pgx/v5/stdlib"')
text = text.replace('"github.com/masahitojp/mariamem"', '"github.com/shibukawa/pgmem"')
text = text.replace("mariamem.Start", "pgmem.Start")
text = text.replace("mariamem.Options{}", 'pgmem.Options{Database: "app"}')
text = text.replace('sql.Open("mysql"', 'sql.Open("pgx"').replace(" ENGINE=InnoDB", "")
(consumer / "main.go").write_text(text)
(consumer / "main_test.go").write_text(
    'package main\nimport "testing"\nfunc TestConsumer(t *testing.T){if e:=smoke();e!=nil{t.Fatal(e)}}\n'
)
(consumer / "go.mod").write_text(
    "module example.com/pgmem-direct-consumer\n\ngo 1.26.0\n\nrequire (\n"
    + MODULE + " " + VERSION + "\n github.com/jackc/pgx/v5 v5.11.0\n)\n"
)
result = {
    "module": MODULE,
    "tag": VERSION,
    "consumer": str(consumer),
    "proxy": "https://proxy.golang.org,direct",
    "sumdb": "sum.golang.org",
    "source_bytes": sum(f.stat().st_size for f in source.rglob("*") if f.is_file()),
    "module_zip_bytes": archive.stat().st_size,
    "module_zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
}
(work / "fixtures.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
