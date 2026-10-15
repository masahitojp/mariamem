"""Isolated Go producer -> Python owner -> Go consumers. No database benchmark."""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import threading
import time

B = 16384
IDENTITY = "d-component-fixture-v1"


def expected(manifest):
    return {n: (v["size"], v["hash"]) for n, v in manifest["files"].items()}


class Owner:
    """Own exact verified unlinked read-only FDs, serialized borrow/close."""
    def __init__(self):
        self.fds = []
        self.lock = threading.RLock()
        self.closed = False

    @classmethod
    def acquire(cls, root, manifest, source_expected, parent=None, fault=None):
        obj = cls()
        try:
            m = copy.deepcopy(manifest)
            if m["identity"] != IDENTITY or expected(m) != source_expected:
                raise ValueError("identity/inventory/expected mismatch")
            sizes = m["segments"]
            if not sizes or any(type(n) is not int or n < 0 or n > 1 << 30 or n % B for n in sizes):
                raise ValueError("segment sizes")
            if parent is not None:
                with parent.lock:
                    if parent.closed:
                        raise ValueError("parent closed")
                    if sizes[:-1] != parent.manifest["segments"]:
                        raise ValueError("parent inventory")
                    for fd in parent.fds:
                        obj.fds.append(os.dup(fd))
            elif len(sizes) != 1:
                raise ValueError("unexpected parent")
            if {p.name for p in root.iterdir()} != {"segment"}:
                raise ValueError("segment inventory")
            fd = os.open(root / "segment", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            obj.fds.append(fd)
            if fault == "open":
                raise ValueError("injected open")
            (root / "segment").unlink()
            for fd, size in zip(obj.fds, sizes):
                st = os.fstat(fd)
                import stat
                if not stat.S_ISREG(st.st_mode) or st.st_size != size or st.st_nlink != 0:
                    raise ValueError("backing metadata")
                if fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY:
                    raise ValueError("writable owner")
            if fault == "unlink":
                raise ValueError("injected unlink")
            for name, f in m["files"].items():
                if not name or "/" in name or name in (".", ".."):
                    raise ValueError("file name")
                size = f["size"]
                if type(size) is not int or not 0 <= size <= 1 << 30 or len(f["refs"]) != (size + B - 1) // B:
                    raise ValueError("logical range")
                for r in f["refs"]:
                    seg, off = r["seg"], r["off"]
                    if type(seg) is not int or type(off) is not int:
                        raise ValueError("reference type")
                    if seg == -1 and off == 0:
                        continue
                    if seg < 0 or seg >= len(sizes) or off < 0 or off % B or off > sizes[seg] - B:
                        raise ValueError("reference range")
            obj.manifest = m
            obj.verify()
            if fault == "hash":
                raise ValueError("injected after hash")
            return obj
        except BaseException:
            obj.close()
            raise

    def chunks(self, f):
        zero = bytes(B)
        for i, r in enumerate(f["refs"]):
            n = min(B, f["size"] - i * B)
            p = zero[:n] if r["seg"] == -1 else os.pread(self.fds[r["seg"]], n, r["off"])
            if len(p) != n:
                raise ValueError("short read")
            yield p

    def verify(self):
        for f in self.manifest["files"].values():
            h = hashlib.sha256()
            for p in self.chunks(f):
                h.update(p)
            if h.hexdigest() != f["hash"]:
                raise ValueError("content mismatch")

    def spawn(self, binary, mode, directory, derive=False, wait=False):
        with self.lock:
            if self.closed:
                raise ValueError("closed")
            for fd, size in zip(self.fds, self.manifest["segments"]):
                st = os.fstat(fd)
                if st.st_size != size or st.st_nlink != 0:
                    raise ValueError("metadata changed")
            p = subprocess.Popen([str(binary), "child", mode, str(directory), "unused"],
                                 pass_fds=self.fds, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            p.stdin.write(json.dumps({"manifest": self.manifest, "fds": self.fds,
                                      "derive": derive, "wait": wait}) + "\n")
            p.stdin.flush()
            return p

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            for fd in self.fds:
                os.close(fd)
            self.fds = []


def finish(p, resume=False):
    out, err = p.communicate("go\n" if resume else None, timeout=30)
    if p.returncode:
        raise RuntimeError(err)
    return json.loads(out)


def produce(binary, mode, root, blocks, stride, fault=None):
    env = os.environ.copy()
    env.pop("D_FAULT", None)
    if fault:
        env["D_FAULT"] = fault
    p = subprocess.run([str(binary), "produce", mode, str(root), str(blocks), str(stride)],
                       capture_output=True, text=True, timeout=30, env=env)
    if fault:
        assert (p.returncode == 42 if fault == "crash" else p.returncode and "injected" in p.stderr), p.stderr
        return
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout)


def model(blocks, stride):
    data = bytearray(blocks * B)
    for i in range(0, blocks, stride):
        data[i*B:(i+1)*B] = bytes((i*17 + j*13 + 7) % 251 for j in range(B))
    tail = bytearray(B+6)
    tail[B-3:] = b"tail-data"
    return {"data": data, "tail": tail, "zeros": bytearray(2*1024*1024), "empty": bytearray()}


def mutated(m):
    m = copy.deepcopy(m)
    for off in (0, B-8, 2*B, 7*B+11):
        payload = b"child-private-update-0123456789AB"
        m["data"][off:off+len(payload)] = payload
    m["tail"] = m["tail"][:2] + bytes(B+4)
    m["new"] = bytearray(b"\0\0\0created")
    return m


def model_expected(m):
    return {n: (len(b), hashlib.sha256(b).hexdigest()) for n, b in m.items()}


def probe_expected(m):
    return {str(off): m["data"][off:off+32].hex() for off in (0, B-8, 2*B, 7*B+11)}


def fdcount():
    return len(os.listdir("/dev/fd"))


def boundaries(binary, scratch):
    checks = []
    for mode in ("d1", "d2"):
        startfds = fdcount()
        with tempfile.TemporaryDirectory(dir=scratch) as t:
            root = Path(t)
            base = root / "base"
            base.mkdir()
            r = produce(binary, mode, base, 32, 4)
            oracle = model(32, 4)
            assert expected(r["manifest"]) == model_expected(oracle)
            owner = Owner.acquire(base, r["manifest"], model_expected(oracle))
            # Derive Q, independently duplicate the parent FDs, then close P.
            qdir = root / "q"
            qdir.mkdir()
            qresult = finish(owner.spawn(binary, mode, qdir, derive=True))
            assert qresult["probes"] == probe_expected(oracle)
            qmodel = mutated(oracle)
            assert expected(qresult["manifest"]) == model_expected(qmodel)
            q = Owner.acquire(qdir, qresult["manifest"], model_expected(qmodel), parent=owner)
            processes = []
            for i in range(2):
                d = root / f"child{i}"
                d.mkdir()
                p = owner.spawn(binary, mode, d, wait=True)
                assert json.loads(p.stdout.readline()) == {"ready": True}
                processes.append(p)
            owner.close()
            for p in processes:
                assert finish(p, True)["probes"] == probe_expected(oracle)
            try:
                owner.spawn(binary, mode, root)
                raise AssertionError("closed parent accepted")
            except ValueError:
                pass
            q.verify()
            d = root / "qchild"
            d.mkdir()
            p = q.spawn(binary, mode, d, wait=True)
            assert json.loads(p.stdout.readline()) == {"ready": True}
            q.close()
            assert finish(p, True)["probes"] == probe_expected(qmodel)
        assert fdcount() == startfds
        checks.append({"mode": mode, "check": "model/derived/parent-close/two-live-children/cleanup", "status": "PASS"})
        # Race admission against Close; either rejection or a usable independent child.
        admitted, rejected = 0, 0
        for repeat in range(8):
            with tempfile.TemporaryDirectory(dir=scratch) as t:
                root = Path(t)
                base, child = root / "base", root / "child"
                base.mkdir()
                child.mkdir()
                r = produce(binary, mode, base, 32, 4)
                owner = Owner.acquire(base, r["manifest"], expected(r["manifest"]))
                barrier = threading.Barrier(2)
                outcome, failures = [], []
                def admit():
                    barrier.wait()
                    try:
                        outcome.append(owner.spawn(binary, mode, child))
                    except ValueError as exc:
                        if str(exc) != "closed":
                            failures.append(str(exc))
                worker = threading.Thread(target=admit)
                worker.start()
                barrier.wait()
                owner.close()
                worker.join(timeout=10)
                assert not worker.is_alive() and not failures
                for p in outcome:
                    assert finish(p)["probes"] == probe_expected(oracle)
                admitted += len(outcome)
                rejected += not outcome
            assert fdcount() == startfds
        checks.append({"mode": mode, "check": "spawn-close-race-8", "status": "PASS", "admitted": admitted, "rejected": rejected})
        for fault in ("bytes", "swap", "missing-ref", "outside", "overflow", "negative", "wrong-guest", "extra-file", "missing-file", "extra-segment", "missing-segment", "open", "unlink", "hash"):
            before = fdcount()
            with tempfile.TemporaryDirectory(dir=scratch) as t:
                root = Path(t)
                r = produce(binary, mode, root, 32, 1)
                m = r["manifest"]
                exp = expected(m)
                if fault == "bytes":
                    os.chmod(root / "segment", 0o600)
                    with open(root / "segment", "r+b") as f:
                        f.write(b"BAD!")
                elif fault == "swap":
                    refs = m["files"]["data"]["refs"]
                    refs[0], refs[1] = refs[1], refs[0]
                elif fault == "missing-ref":
                    m["files"]["data"]["refs"].pop()
                elif fault in ("outside", "overflow", "negative"):
                    m["files"]["data"]["refs"][0]["off"] = {"outside": m["segments"][0], "overflow": 1 << 64, "negative": -B}[fault]
                elif fault == "wrong-guest":
                    m["identity"] = "other"
                elif fault == "extra-file":
                    m["files"]["extra"] = copy.deepcopy(m["files"]["data"])
                elif fault == "missing-file":
                    del m["files"]["data"]
                elif fault == "extra-segment":
                    (root / "extra").write_bytes(b"extra")
                elif fault == "missing-segment":
                    (root / "segment").unlink()
                try:
                    Owner.acquire(root, m, exp, fault=fault)
                    raise AssertionError("fault accepted: " + fault)
                except ValueError:
                    pass
            assert fdcount() == before
            checks.append({"mode": mode, "check": fault, "status": "PASS"})
        for fault in ("transfer", "after-freeze", "crash"):
            with tempfile.TemporaryDirectory(dir=scratch) as t:
                produce(binary, mode, Path(t), 32, 1, fault=fault)
            checks.append({"mode": mode, "check": "producer-"+fault, "status": "PASS"})
    assert not list(scratch.iterdir())
    return checks


def trial(binary, scratch, mode, blocks, stride):
    start = time.perf_counter_ns()
    with tempfile.TemporaryDirectory(dir=scratch) as t:
        root = Path(t)
        base = root / "base"
        base.mkdir()
        result = produce(binary, mode, base, blocks, stride)
        produced = time.perf_counter_ns()
        owner = Owner.acquire(base, result["manifest"], expected(result["manifest"]))
        acquired = time.perf_counter_ns()
        children = []
        child_wall_ns = []
        for i in range(2):
            begin = time.perf_counter_ns()
            d = root / f"child{i}"
            d.mkdir()
            children.append(finish(owner.spawn(binary, mode, d)))
            child_wall_ns.append(time.perf_counter_ns()-begin)
        assert children[0]["probes"] == children[1]["probes"]
        done = time.perf_counter_ns()
        audit_start = time.perf_counter_ns()
        owner.verify()
        audit_ns = time.perf_counter_ns() - audit_start
        owner.close()
    end = time.perf_counter_ns()
    m = result.pop("manifest")
    return {"mode": mode, "blocks": blocks, "stride": stride,
            "logical_bytes": sum(f["size"] for f in m["files"].values()),
            "verification_bytes_per_pass": sum(f["size"] for f in m["files"].values()),
            "segments": len(m["segments"]), "owner_fds": len(m["segments"]),
            "total_ns": end-start-audit_ns, "post_children_audit_ns_excluded": audit_ns,
            "producer_wall_ns": produced-start,
            "acquire_ns": acquired-produced, "children_wall_ns": done-acquired,
            "cleanup_ns": end-done-audit_ns, "child_wall_ns": child_wall_ns,
            "producer": result, "children": children}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--boundaries-only", action="store_true")
    ap.add_argument("--summarize-only", action="store_true")
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.scratch.mkdir(parents=True, exist_ok=True)
    if args.summarize_only:
        summarize(args.output)
        return
    checks = boundaries(args.binary, args.scratch)
    (args.output / "boundaries.json").write_text(json.dumps(checks, indent=2)+"\n")
    print(f"boundary checks: {len(checks)} PASS", flush=True)
    if args.boundaries_only:
        return
    rows, pilots = [], []
    for blocks in (512, 4096):
        for stride in (1, 16):
            for mode in ("d1", "d2"):
                pilots.append(trial(args.binary, args.scratch, mode, blocks, stride))
            for repeat in range(5):
                for mode in (("d1", "d2") if repeat % 2 == 0 else ("d2", "d1")):
                    row = trial(args.binary, args.scratch, mode, blocks, stride)
                    row["repeat"] = repeat
                    rows.append(row)
                print(f"blocks={blocks} stride={stride} repeat={repeat} done", flush=True)
    (args.output / "raw.json").write_text(json.dumps(rows, indent=2)+"\n")
    (args.output / "pilots.json").write_text(json.dumps(pilots, indent=2)+"\n")
    summarize(args.output)
    assert not list(args.scratch.iterdir())


def summarize(output):
    rows = json.loads((output / "raw.json").read_text())
    summary = []
    for blocks in (512, 4096):
        for stride in (1, 16):
            group = {m: [r for r in rows if r["blocks"] == blocks and r["stride"] == stride and r["mode"] == m] for m in ("d1", "d2")}
            v = {"blocks": blocks, "stride": stride}
            for mode, rs in group.items():
                assert len(rs) == 5 and [r["repeat"] for r in rs] == list(range(5))
                v[mode] = {k: statistics.median(r[k] for r in rs)/1e6 for k in ("total_ns", "acquire_ns", "children_wall_ns", "cleanup_ns")}
                v[mode].update({k: statistics.median(r["producer"][k] for r in rs)/1e6 for k in ("prepare_ns", "source_hash_ns", "freeze_ns")})
                v[mode]["total_range_ms"] = [min(r["total_ns"] for r in rs)/1e6, max(r["total_ns"] for r in rs)/1e6]
                v[mode]["producer_stats"] = {k: statistics.median(r["producer"]["stats"][k] for r in rs) for k in rs[0]["producer"]["stats"]}
                v[mode]["child_stats"] = {k: statistics.median(c["stats"][k] for r in rs for c in r["children"]) for k in rs[0]["children"][0]["stats"]}
            diffs = [(b["total_ns"]-a["total_ns"])/1e6 for a,b in zip(group["d1"],group["d2"])]
            v["paired_d2_minus_d1_ms"] = diffs
            v["d2_faster_pairs"] = sum(d < 0 for d in diffs)
            summary.append(v)
    (output / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    (output / "environment.json").write_text(json.dumps({"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version(), "ubuntu_x86_64": "SKIP: available Docker host is Linux aarch64; no native x86_64 runner used"}, indent=2)+"\n")


if __name__ == "__main__":
    main()
