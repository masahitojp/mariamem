#!/usr/bin/env python3
"""Build disposable v0.5.0 ON/OFF argv prototypes from exact release Go."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT.parent
RELEASE = Path("/private/tmp/mariamem-v050-release-clone")
SOURCE_COMMIT = "44100ec676c8c9064f32f3a01bd9a990d487bb61"
SOURCE_GO_SHA256 = "8f99ee297e51ccfddfb5920c2618fd73250d5978fdf6e7076ffecc8012a22667"
RELATIVE = Path("internal/generatedgo/code/p5/p5_pure.go")
ANCHOR = "\t\t\t\t\t\tv107 = Fn5726(m, int32(25), v8)\n"
PROBE = '''package main
import (
    "context"
    "database/sql"
    "fmt"
    "github.com/masahitojp/mariamem"
    _ "github.com/go-sql-driver/mysql"
)
func main() {
    db, err := mariamem.Start(context.Background(), mariamem.Options{})
    if err != nil { panic(err) }
    p, err := sql.Open("mysql", db.DSN())
    if err != nil { panic(err) }
    var setting int
    if err := p.QueryRow("SELECT @@GLOBAL.innodb_flush_sync").Scan(&setting); err != nil { panic(err) }
    fmt.Println(setting)
    if err := p.Close(); err != nil { panic(err) }
    if err := db.WaitDisconnected(context.Background()); err != nil { panic(err) }
    if err := db.Close(); err != nil { panic(err) }
}
'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], cwd: Path) -> None:
    print("running", *command, "in", cwd, flush=True)
    env = os.environ.copy()
    env["GOTOOLCHAIN"] = "go1.26.8"
    env["CGO_ENABLED"] = "1"
    subprocess.run(command, cwd=cwd, env=env, check=True)


def copy_needed(target: Path) -> None:
    if target.exists():
        raise SystemExit(f"refusing existing staging directory: {target}")
    target.mkdir(parents=True)
    for name in ("go.mod", "go.sum", "connection.go", "errors.go", "mariamem.go", "snapshot.go"):
        shutil.copy2(RELEASE / name, target / name)
    shutil.copytree(RELEASE / "internal", target / "internal")
    shutil.copytree(RELEASE / "benchmarks/ownedprepared", target / "benchmarks/ownedprepared")


def main() -> None:
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=RELEASE, text=True).strip() != SOURCE_COMMIT:
        raise SystemExit("release source commit differs")
    if sha(RELEASE / RELATIVE) != SOURCE_GO_SHA256:
        raise SystemExit("release generated Go differs")
    evidence = WORK / "evidence"
    temp = WORK / "temp"
    if (evidence / "config-build.json").exists():
        raise SystemExit("refusing to overwrite config-build.json")
    records = {"source_commit": SOURCE_COMMIT, "generated_go_sha256": SOURCE_GO_SHA256,
               "method": "disposable translated-Go argv append; original 25 args preserved; unqualified"}
    for value in (1, 0):
        arm = f"flush-sync-{value}"
        stage = temp / f"source-{arm}"
        copy_needed(stage)
        target = stage / RELATIVE
        original = target.read_text()
        if original.count(ANCHOR) != 1:
            raise SystemExit(f"argv call anchor count: {original.count(ANCHOR)}")
        # l4m_open has a 26-pointer array (25 args plus terminator). Its final
        # slot receives a new pointer. Reserve 32 bytes below its stack frame
        # during mysql_server_init so nested calls cannot overwrite the string.
        replacement = f'''\t\t\t\t\t\t// Experiment only: append one InnoDB setting without removing original args.
\t\t\t\t\t\textraArg := []byte("--innodb-flush-sync={value}\\x00")
\t\t\t\t\t\textraAddr := v8 - int32(32)
\t\t\t\t\t\tcopy(m.Memory[uint32(extraAddr):uint32(extraAddr)+uint32(len(extraArg))], extraArg)
\t\t\t\t\t\t*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v8)), 100, 4))) = extraAddr
\t\t\t\t\t\tm.G0 = extraAddr
\t\t\t\t\t\tv107 = Fn5726(m, int32(26), v8)
\t\t\t\t\t\tm.G0 = v8
'''
        target.write_text(original.replace(ANCHOR, replacement))
        probe_source = stage / "benchmarks/config_probe/main.go"
        probe_source.parent.mkdir()
        probe_source.write_text(PROBE)
        output = temp / f"ownedprepared-{arm}"
        probe = temp / f"probe-{arm}"
        run(["go", "build", "-p", "1", "-trimpath", "-buildvcs=false", "-o", str(output), "./benchmarks/ownedprepared"], stage)
        run(["go", "build", "-p", "1", "-trimpath", "-buildvcs=false", "-o", str(probe), "./benchmarks/config_probe"], stage)
        observed = subprocess.check_output([str(probe)], cwd=stage, text=True).strip()
        if observed != str(value):
            raise SystemExit(f"{arm}: SQL observed {observed}, wanted {value}")
        records[arm] = {"generated_go_sha256": sha(target), "binary_sha256": sha(output),
                        "probe_sha256": sha(probe), "sql_setting": observed,
                        "argv_count": 26, "appended_arg": f"--innodb-flush-sync={value}"}
        shutil.rmtree(stage)
        print(arm, records[arm], flush=True)
    (evidence / "config-build.json").write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    main()
