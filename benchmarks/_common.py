"""Small lifecycle helpers for optional benchmarks; no performance thresholds."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmarks/results"


def positive(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return result


def options(description, *, seeded=False, parallel=False, memory=False):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--backend", choices=("mariamem", "testcontainers", "both"), default="mariamem")
    parser.add_argument("--runs", type=positive, default=3 if parallel else 10)
    parser.add_argument("--warmup", type=int, default=1, help="unmeasured runs per backend/worker count")
    parser.add_argument("--image", default="mariadb:12.3", help="prefer an immutable image digest")
    parser.add_argument("--json", type=Path, help="default: benchmarks/results/<script>-<timestamp>.json")
    if seeded:
        parser.add_argument("--rows", type=positive, default=1000)
    if parallel:
        parser.add_argument("--workers", nargs="+", type=positive, default=[1, 2, 4, 8])
    if memory:
        parser.add_argument("--hold", type=float, default=30, help="seconds to retain all ready DBs")
        parser.add_argument("--interval", type=float, default=0.2, help="requested sampling interval in seconds")
    args = parser.parse_args()
    if args.warmup < 0:
        parser.error("--warmup must be nonnegative")
    if memory and (not 0 <= args.hold < float("inf") or not 0 < args.interval < float("inf")):
        parser.error("--hold must be finite/nonnegative; --interval must be finite/positive")
    if args.json is not None:
        dest = args.json.resolve()
        if dest.is_relative_to(ROOT) and not dest.is_relative_to(RESULTS):
            parser.error("repository-local output must be under benchmarks/results/")
    return args


def backends(args):
    return ("mariamem", "testcontainers") if args.backend == "both" else (args.backend,)


def environment(args):
    versions = {}
    for name in ("mariamem", "PyMySQL", "testcontainers", "docker"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    result = {"python": platform.python_version(), "platform": platform.platform(),
              "machine": platform.machine(), "cpu_count": os.cpu_count(), "packages": versions}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    result["commit"] = commit.stdout.strip() if commit.returncode == 0 else None
    result["working_tree_dirty"] = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    if "mariamem" in backends(args):
        import mariamem
        native = Path(os.environ.get("MARIAMEM_NATIVE_DIR", Path(mariamem.__file__).parent / "_native"))
        result["native_override"] = "MARIAMEM_NATIVE_DIR" in os.environ
        result["native_manifest"] = json.loads((native / "manifest.json").read_text())
    if "testcontainers" in backends(args):
        from docker.errors import ImageNotFound
        from testcontainers.core.config import testcontainers_config as config
        from testcontainers.core.container import Reaper
        from testcontainers.core.docker_client import DockerClient
        client = DockerClient().client
        try:
            # All image downloads (including Ryuk) happen before any benchmark timer.
            for image in [args.image] + ([] if config.ryuk_disabled else [config.ryuk_image]):
                try:
                    client.images.get(image)
                except ImageNotFound:
                    print(f"Preflight: pulling {image} (outside measurement)", flush=True)
                    client.images.pull(image)
            image = client.images.get(args.image)
            args.resolved_image = image.id
            info = client.info()
            result["docker"] = {key: info.get(key) for key in
                                ("ServerVersion", "OperatingSystem", "Architecture", "NCPU", "MemTotal")}
            result["image"] = {"requested": args.image, "id": image.id,
                               "digests": image.attrs.get("RepoDigests", [])}
            result["ryuk_disabled"] = config.ryuk_disabled
            if not config.ryuk_disabled:
                Reaper.get_instance()  # Reaper setup is also excluded from DB timings.
        finally:
            client.close()
    return result


@contextmanager
def instance(backend, args, snapshot=None, label=None):
    if backend == "mariamem":
        import mariamem
        started = time.perf_counter_ns() if os.environ.get("MARIAMEM_TIMING_DIR") else None
        with (snapshot.fork() if snapshot is not None else mariamem.start()) as db:
            value = SimpleNamespace(info=db.connection_info(), database=db)
            if started is not None:
                value.timing_start = started
                value.timing_events = [{"name": "begin", "offset_ns": 0},
                    {"name": "database_returned", "offset_ns": time.perf_counter_ns() - started}]
            yield value
    else:
        from testcontainers.core.container import DockerContainer
        container = (DockerContainer(args.resolved_image)
                     .with_env("MARIADB_ROOT_PASSWORD", "benchmark-only")
                     .with_env("MARIADB_DATABASE", "test")
                     .with_env("MARIADB_ROOT_HOST", "%")
                     .with_exposed_ports(3306))
        if label:
            container.with_kwargs(labels={"mariamem.benchmark": label})
        try:
            container.start()
            yield SimpleNamespace(info={"host": container.get_container_host_ip(),
                                        "port": int(container.get_exposed_port(3306)),
                                        "user": "root", "password": "benchmark-only", "database": "test"})
        finally:
            container.stop()


def probe(db, *, rows=None, seed=False):
    import pymysql
    deadline = time.perf_counter() + 120
    while True:
        try:
            connection = pymysql.connect(**db.info, connect_timeout=1, read_timeout=30, write_timeout=30)
            break
        except pymysql.OperationalError:
            if time.perf_counter() >= deadline:
                raise
            time.sleep(0.02)
    if hasattr(db, "timing_events"):
        db.timing_events.append({"name": "client_connected", "offset_ns": time.perf_counter_ns() - db.timing_start})
    with connection, connection.cursor() as cur:
        if seed:
            cur.execute("CREATE TABLE benchmark_rows(id INT PRIMARY KEY, payload VARCHAR(64)) ENGINE=InnoDB")
            for start in range(0, rows, 1000):
                cur.executemany("INSERT INTO benchmark_rows VALUES(%s,%s)",
                                [(i, "x" * 32) for i in range(start, min(start + 1000, rows))])
            connection.commit()
        cur.execute("SELECT 1" if rows is None else "SELECT COUNT(*) FROM benchmark_rows")
        expected = 1 if rows is None else rows
        if cur.fetchone() != (expected,):
            raise AssertionError("unexpected SQL result")
        completed = time.perf_counter()
        if hasattr(db, "timing_events"):
            db.timing_events.append({"name": "first_sql", "offset_ns": time.perf_counter_ns() - db.timing_start})
        # Record the actual DB version after the readiness timing boundary.
        cur.execute("SELECT VERSION()")
        version = cur.fetchone()[0]
    return completed, version


@contextmanager
def template(backend, args, report, phase):
    if backend == "testcontainers":
        yield None
        return
    started = time.perf_counter()
    with instance(backend, args) as db:
        probe(db, rows=args.rows, seed=True)
        db.database.wait_disconnected()
        with db.database.snapshot() as saved:
            elapsed = time.perf_counter() - started
            report["preparations"].append({"backend": backend, "phase": phase,
                                           "seconds": elapsed})
            print(f"{backend} {phase}: template preparation={elapsed:.3f}s", flush=True)
            yield saved


def one(backend, args, *, snapshot=None, seeded=False):
    started = time.perf_counter()
    with instance(backend, args, snapshot) as db:
        ready, version = probe(db, rows=args.rows if seeded else None,
                               seed=seeded and backend == "testcontainers")
        cleanup = time.perf_counter()
    return {"ready_seconds": ready - started, "cleanup_seconds": time.perf_counter() - cleanup,
            "server_version": version}


def record(report, backend, phase, run, result, workers=1):
    row = {"backend": backend, "phase": phase, "run": run, "workers": workers, **result}
    report["samples"].append(row)
    print(f"{backend:14} {phase:11} run={run + 1} DBs={workers} ready={row['ready_seconds']:.3f}s", flush=True)


def run(args, workload, name):
    report = {"benchmark": name, "started_at": datetime.now(timezone.utc).isoformat(),
              "settings": {k: v for k, v in vars(args).items() if k != "json"},
              "preparations": [], "samples": [], "completed": False}
    output = args.json or RESULTS / f"{name}-{time.time_ns()}.json"
    try:
        report["environment"] = environment(args)
        workload(args, report)
        report["completed"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        measured = [s for s in report["samples"] if s["phase"] == "measurement"]
        report["summary"] = []
        for backend, workers in sorted({(s["backend"], s["workers"]) for s in measured}):
            times = [s["ready_seconds"] for s in measured if (s["backend"], s["workers"]) == (backend, workers)]
            summary = {"backend": backend, "workers": workers, "runs": len(times),
                       "min_seconds": min(times), "median_seconds": statistics.median(times),
                       "mean_seconds": statistics.mean(times), "max_seconds": max(times),
                       "sum_ready_seconds": sum(times)}
            report["summary"].append(summary)
            print(f"{backend}, {workers} DB(s): median={summary['median_seconds']:.3f}s "
                  f"mean={summary['mean_seconds']:.3f}s range={min(times):.3f}..{max(times):.3f}s")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(f"Raw results: {output}")


def stage_timings(db, operation="startup"):
    """Read structured benchmark diagnostics after the primary SQL timestamp."""
    if not os.environ.get("MARIAMEM_TIMING_DIR"):
        return None
    result = {"caller": getattr(db, "timing_events", []),
              "python_startup": getattr(db.database, "_startup_timing", None)}
    root = Path(os.environ["MARIAMEM_TIMING_DIR"])
    pattern = f"{db.database.diagnostics['host_pid']}-{operation}-*.json"
    try:
        paths = list(root.glob(pattern))
        if len(paths) != 1:
            raise ValueError(f"expected one record; got {len(paths)}")
        result["host"] = json.loads(paths[0].read_text())
        guest = result["host"].get("guest")
        if operation == "startup" and (guest is not None or os.environ.get("MARIAMEM_REQUIRE_GUEST_TIMING")):
            validate_guest_timing(guest)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"stage timing requires an instrumented host; missing/invalid structured trace: {root / pattern}") from exc
    return result


def validate_guest_timing(record):
    """Reject absent/malformed guest diagnostics instead of reporting empty stages."""
    expected = ["guest_main", "restore_begin", "restore_complete", "open_begin",
                "server_init_begin", "server_init_complete", "bootstrap_complete", "ready_prepared"]
    if not isinstance(record, dict) or record.get("version") != 1 or record.get("clock") != "guest_monotonic":
        raise ValueError("guest stage timing requires a matching instrumented guest")
    events = record.get("events", [])
    offsets = [event.get("offset_ns") for event in events]
    if ([event.get("name") for event in events] != expected or len(offsets) != len(expected)
            or any(type(value) is not int or value < 0 for value in offsets)
            or offsets != sorted(offsets) or offsets[0] != 0):
        raise ValueError("invalid guest startup event sequence/monotonic offsets")
