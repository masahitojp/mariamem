#!/usr/bin/env python3
"""Link the same MySQL SQL consumer without mariamem (compile-only baseline)."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument("--work", type=Path, required=True)
p.add_argument("--go", type=Path, required=True)
p.add_argument("--cache-label", default="go126-ci")
a = p.parse_args()
work = a.work.resolve()
consumer = Path(tempfile.mkdtemp(prefix="mysql-driver-baseline-"))
text = (Path(__file__).parent / "consumer.go.txt").read_text()
text = text.replace('\t"github.com/masahitojp/mariamem"\n', "")
start = text.index("\tdb, e := mariamem.Start")
end = text.index("\tif e != nil", text.index("\tpool, e :=", start))
text = text[:start] + '\tpool, e := sql.Open("mysql", "root@tcp(127.0.0.1:1)/mysql")\n' + text[end:]
text = text.replace('\t"context"\n', "").replace("return db.Close()", "return pool.Close()")
(consumer / "main.go").write_text(text)
(consumer / "go.mod").write_text(
    "module example.com/mysql-driver-baseline\n\ngo 1.26.0\n"
    "require github.com/go-sql-driver/mysql v1.9.3\n"
)
env = dict(os.environ, GOWORK="off", GOENV="off", GOTOOLCHAIN="local",
           CGO_ENABLED="0", GOCACHE=str(work / (a.cache_label + "-cache")),
           GOMODCACHE=str(work / "mod-cache"), GOPROXY=(work / "proxy").as_uri(),
           GOSUMDB="off", GOFLAGS="", GOEXPERIMENT="")
sizes = {}
for label, flags in (("default", []), ("stripped", ["-ldflags=-s -w"])):
    out = work / ("driver-baseline-" + label)
    subprocess.run([str(a.go.resolve()), "build", "-mod=mod", *flags, "-o", str(out), "."],
                   cwd=consumer, env=env, check=True)
    sizes[label + "_bytes"] = out.stat().st_size
(work / "baseline.json").write_text(json.dumps(sizes, indent=2) + "\n")
print(json.dumps(sizes))
