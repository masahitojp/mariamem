"""Package byte-preserved mutex, CV and rwlock guest functions for bounded investigation.

Packaging/TLS fixture differs from the complete guest; no production edits.
Host wait/wake methods and base sources are copied unchanged and hash-bound.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

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
    seen, todo = set(), [69, 93, 130, 202, 203, 209, 210, 211, 212, 213, 218, 220, 226, 4052]
    while todo:
        fn = todo.pop()
        if fn in seen:
            continue
        seen.add(fn)
        todo.extend(graph[str(fn)]["direct_callees"])
    assert seen == {69, 71, 80, 88, 89, 90, 93, 94, 130, 202, 203, 209, 210, 211, 212, 213, 218, 220, 226, 4052}, "dependency scope changed"
    assert all(not graph[str(fn)]["indirect_calls"] for fn in seen)
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
    shutil.copyfile(Path(__file__).with_name("protocol_test.go.txt"), fixture / "probe_test.go")
    shutil.copyfile(Path(__file__).with_name("timeout_test.go.txt"), module / "internal/generatedgo/code/base/audit_timeout_test.go")
    shutil.copyfile(Path(__file__).with_name("thread_boundary_test.go.txt"), module / "internal/generatedgo/code/base/audit_thread_boundary_test.go")
    (module / "internal/generatedgo/code/base/audit_support.go").write_text("package base\nfunc AuditParked(m *Module, ea uint64) int { m.Threads.parkMu.Lock(); defer m.Threads.parkMu.Unlock(); return len(m.Threads.parked[ea]) }\n")
    (out / "identities.json").write_text(json.dumps({"functions": identities, "copied_source_sha256": copied,
        "host_source_sha256": digest(source), "host_methods_sha256": [hashlib.sha256(s.encode()).hexdigest() for s in methods],
        "fixture_sha256": digest(Path(__file__).with_name("protocol_test.go.txt")),
        "timeout_fixture_sha256": digest(Path(__file__).with_name("timeout_test.go.txt")),
        "thread_boundary_fixture_sha256": digest(Path(__file__).with_name("thread_boundary_test.go.txt")),
        "scope": "20 unmodified guest function bodies and canonical host/base; isolated TLS/module, not full SQL guest"}, indent=2) + "\n")
    print(module)


if __name__ == "__main__":
    main()
