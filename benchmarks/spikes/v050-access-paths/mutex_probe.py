"""Execute byte-preserved real-guest mutex dependency functions in isolation.

Packaging/TLS fixture differs from the complete guest; no production edits.
Host wait/wake methods and base sources are copied unchanged and hash-bound.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def host_method(text, name):
    start = text.index("func (h *host) " + name + "(")
    lines = text[start:].splitlines(keepends=True)
    level = 0
    for i, line in enumerate(lines):
        level += line.count("{") - line.count("}")
        if level == 0:
            return "".join(lines[:i + 1])
    raise ValueError("method end missing")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    graph = json.loads((a.scan / "direct-call-graph.json").read_text())
    seen, todo = set(), [93, 130]
    while todo:
        fn = todo.pop()
        if fn in seen:
            continue
        seen.add(fn)
        todo.extend(graph[str(fn)]["direct_callees"])
    assert seen == {88, 89, 90, 93, 130}, "mutex dependency scope changed"
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    module = out / "module"
    module.mkdir()
    (module / "go.mod").write_text("module github.com/masahitojp/mariamem\n\ngo 1.26.0\n")
    copied = {}
    for folder in ("internal/generatedgo/code/base", "internal/prepared"):
        dest = module / folder
        dest.mkdir(parents=True)
        for src in (ROOT / folder).iterdir():
            if src.suffix not in {".go", ".s"} or src.name.endswith("_test.go"):
                continue
            shutil.copyfile(src, dest / src.name)
            copied[src.relative_to(ROOT).as_posix()] = digest(src)
    fixture = module / "probe"
    fixture.mkdir()
    definitions, identities = [], {}
    for fn in sorted(seen):
        info = graph[str(fn)]
        file = ROOT / info["file"]
        lines = file.read_text().splitlines(keepends=True)
        start = info["line"] - 1
        end = next((i for i in range(start + 1, len(lines))
                    if re.match(r"func Fn\d+\(", lines[i])), len(lines))
        body = "".join(lines[start:end])
        assert body.startswith(f"func Fn{fn}(")
        definitions.append(body)
        identities[str(fn)] = {"file": info["file"], "line": info["line"], "symbol": info["symbol"],
                              "body_sha256": hashlib.sha256(body.encode()).hexdigest(), "source_sha256": digest(file)}
    (fixture / "guest_functions.go").write_text('package probe\nimport ("unsafe";"github.com/masahitojp/mariamem/internal/generatedgo/code/base")\n' + "\n".join(definitions))
    source = ROOT / "internal/generatedgo/main.go"
    methods = [host_method(source.read_text(), n) for n in ("Futex_wait", "futexWake", "Futex_wake", "Futex_wake_all")]
    interface = (ROOT / "internal/generatedgo/code/base/base.go").read_text().split("type Wasix_32v1Imports interface {", 1)[1].split("\n}", 1)[0]
    unused = []
    for line in interface.splitlines():
        if not line.strip() or line.strip().startswith(("Futex_wait(", "Futex_wake(", "Futex_wake_all(")):
            continue
        unused.append("func (h *host) " + line.strip().replace("*Module", "*base.Module") + '{panic("unexpected import in isolated mutex path")}')
    (fixture / "host.go").write_text('package probe\nimport ("encoding/binary";"github.com/masahitojp/mariamem/internal/generatedgo/code/base")\ntype host struct{}\n' + "\n".join(methods + unused))
    shutil.copyfile(Path(__file__).with_name("mutex_probe_test.go.txt"), fixture / "probe_test.go")
    env = dict(os.environ, GOTOOLCHAIN="go1.26.8", GOWORK="off", GOENV="off", GOFLAGS="", GOEXPERIMENT="")
    rows = []
    for backing in ("heap", "mmap"):
        for race, observe in ((False, True), (True, True), (False, False)):
            key = backing + ("-race" if race else "") + ("-control" if not observe else "")
            r = subprocess.run(["go", "test", "-p", "1", *(["-race"] if race else []), "-v", "-count=1", "-timeout=30s", "./probe"],
                               cwd=module, env={**env, "PROBE_BACKING": backing, "PROBE_OBSERVE": str(int(observe))}, text=True, capture_output=True, timeout=180)
            log = r.stdout + r.stderr
            (out / (key + ".txt")).write_text(log)
            observations = [json.loads(s.split("OBS ", 1)[1]) for s in log.splitlines() if "OBS " in s]
            assert observations and observations[-1]["value"] == 2000, log[-4000:]
            if observe:
                assert observations[-1]["wait_calls"] > 0, "wait path was not observed"
            reports = log.count("WARNING: DATA RACE")
            assert not re.search(r"\bprobe\.Fn90\b", log), "TLS scaffold produced a cancellation-state race"
            if race and backing == "heap":
                assert r.returncode != 0 and reports > 0, "heap mixed-access positive control did not report"
            else:
                assert r.returncode == 0, log[-4000:]
            rows.append({"key": key, "observe": observe, "exit_code": r.returncode, "race_reports": reports, "observations": observations,
                         "log_sha256": hashlib.sha256(log.encode()).hexdigest()})
            print(key, "value PASS", "exit", r.returncode, "race reports", reports, flush=True)
    (out / "results.json").write_text(json.dumps({"functions": identities, "copied_source_sha256": copied,
        "host_source_sha256": digest(source), "host_methods_sha256": [hashlib.sha256(s.encode()).hexdigest() for s in methods],
        "fixture_sha256": digest(Path(__file__).with_name("mutex_probe_test.go.txt")),
        "go_version": subprocess.check_output(["go", "version"], env=env, text=True).strip(), "checks": rows,
        "scope": "Real guest Fn88/89/90/93/130 bodies and canonical host/base in isolated packaging, 4 agents and NORMAL mutex; not actual SQL execution, all mutex types, alias/lifetime proof or compiler/memory-model proof"}, indent=2) + "\n")


if __name__ == "__main__":
    main()
