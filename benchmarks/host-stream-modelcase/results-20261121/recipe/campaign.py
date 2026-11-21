"""Run the matched suite on macOS. Sample child RSS using Darwin libproc."""
import ctypes
import gzip
import itertools
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

w = Path(sys.argv[1]).resolve()
t = w / "temp"
out = w / "evidence/published"
raw = out / "runs"
raw.mkdir(exist_ok=True)
sys.path.insert(0, str(w / "worktree/scripts"))
from experiment_disk import DiskGuard

guard = DiskGuard(w, min_free_gib=8, budget_gib=8)
names = ("GetOrder ListOrders SearchProducts TopProducts RevenueByCategory "
         "CreateOrder ApplyDiscount DeleteUser ShipOrder CancelOrder").split()
pattern = "^Test(" + "|".join(names) + ")$"
arms = ("os", "both", "pg")
lib = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
lib.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                             ctypes.c_void_p, ctypes.c_int]
buf = ctypes.create_string_buffer(96)

def current_rss(pid):
    if lib.proc_pidinfo(pid, 4, 0, buf, len(buf)) == len(buf):
        return int.from_bytes(buf.raw[8:16], sys.byteorder)
    return 0

def validate(trace):
    spans = trace["spans"]
    counts = Counter(s["kind"] for s in spans)
    for key, n in dict(boot=1, snapshot=1, import_=1, read=50, write=20,
                       fork=21, sample=21, close=21).items():
        assert counts[key.rstrip("_")] == n, (key, counts)
    for name in names:
        lanes = {s["lane"] for s in spans if s["kind"] in ("read", "write")
                 and s["lane"].startswith("Test" + name + "/")}
        assert len(lanes) == (10 if name in names[:5] else 4), (name, lanes)
    assert any(s["kind"] == "close" and s["lane"] == "final" for s in spans)

def run(p, arm, role, block, position):
    label = f"{role}-p{p}-b{block}-{position}-{arm}"
    tracefile = t / (label + ".trace")
    log = t / (label + ".log")
    frames = t / (label + ".frames")
    mode = "pg" if arm == "pg" else ("frames" if role == "frames" else "maria")
    env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
    env.update(GOGC="100", GOMAXPROCS="8", TMPDIR=str(t / "gotmp"),
               MODELCASE_MATCHED="1", MARIA_AUDIT_OF="1", REVENUE_PREAGG="1",
               MARIA_ASYNC_CLOSE="0", SKIP_READ_BODY="0", TRANSPORT_DIAG="0",
               MODELCASE_TRACE=str(tracefile), BENCH_FRAMES=str(frames),
               MARIAMEM_BENCH_STREAM="os" if arm == "pg" else arm)
    semantics = role == "semantics"
    args = [t / (mode + ".test"), "-test.v", "-test.timeout=110s",
            "-test.run=" + ("^TestMatchedSemantics$" if semantics else pattern),
            f"-test.parallel={p}"]
    samples = []
    with log.open("w") as f:
        start = time.monotonic_ns()
        proc = subprocess.Popen(args, env=env, stdout=f, stderr=subprocess.STDOUT)
        try:
            while True:
                pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
                if pid:
                    end = time.monotonic_ns()
                    proc.returncode = os.waitstatus_to_exitcode(status)
                    break
                before = time.time_ns()
                rss = current_rss(proc.pid)
                if rss:
                    samples.append([(before + time.time_ns()) // 2, rss])
                if time.monotonic_ns() - start > 120_000_000_000:
                    raise TimeoutError(label)
                time.sleep(.005)
        finally:
            if proc.returncode is None:
                proc.kill()
                proc.wait()
    lines = log.read_text()
    assert proc.returncode == 0 and "--- SKIP" not in lines, (label, lines[-4000:])
    assert len(samples) > 10 and usage.ru_maxrss >= max(r for _, r in samples)
    trace = json.loads(tracefile.read_text())
    if semantics:
        assert "--- PASS: TestMatchedSemantics " in lines
    else:
        validate(trace)
    data = dict(role=role, p=p, block=block, position=position, arm=arm,
                process_ms=(end-start)/1e6, user_ms=usage.ru_utime*1000,
                system_ms=usage.ru_stime*1000, peak_bytes=usage.ru_maxrss,
                trace=trace, rss=samples, exit=proc.returncode)
    if role == "frames":
        data["frames"] = json.loads(frames.read_text())
        assert sum(data["frames"].values()) > 0
    with gzip.open(raw / (label + ".json.gz"), "wt") as f:
        json.dump(data, f, separators=(",", ":"))
    print(label, round(trace["elapsed_ms"], 2), flush=True)

if __name__ == "__main__":
    assert sys.platform == "darwin" and current_rss(os.getpid()) > 0
    (out / "machine.json").write_text(json.dumps(dict(
        mac=platform.mac_ver()[0], arch=platform.machine(),
        cpu=subprocess.check_output(["sysctl","-n","machdep.cpu.brand_string"], text=True).strip(),
        python=sys.version, interval_ms=5, gomaxprocs=8, gogc=100), indent=2) + "\n")
    guard.check()
    for i, arm in enumerate(arms):
        run(1, arm, "semantics", 0, i)
    for p in (1, 8):
        for i, arm in enumerate(arms):
            run(p, arm, "warm", 0, i)
    for block, order in enumerate(itertools.permutations(arms), 1):
        guard.check()
        for p in ((1, 8) if block % 2 else (8, 1)):
            for i, arm in enumerate(order):
                run(p, arm, "main", block, i)
    for block, order in enumerate((arms[:2], arms[:2][::-1]), 1):
        for p in (1, 8):
            for i, arm in enumerate(order):
                run(p, arm, "frames", block, i)
    print(guard.check(), flush=True)
