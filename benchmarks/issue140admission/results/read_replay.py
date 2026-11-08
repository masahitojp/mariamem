"""Read-only replay of same-instance, same-channel read-wait observations."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent


def summarize(observations):
    result = {"processes": [], "profile_bound_prepares": [], "natural_long_waits": []}
    for run in observations:
        meta = run["trace"]["meta"]
        assert meta["read_cases"] == "50" and meta["write_cases"] == "20"
        assert meta["test_exit"] == "0" and meta["active_mappings_after"] == "0"
        assert meta["innodb_buffer_pool_size"] == str(run["pool_mib"] * 2**20)
        assert meta["innodb_buffer_pool_size_max"] == meta["innodb_buffer_pool_size"]
        assert len(run["loaders"]) == 21
        readers = run["read_observers"]
        assert len(readers) == 22 and len({r["db_id"] for r in readers}) == 22
        scopes = {}
        waits = []
        for reader in readers:
            assert reader["closed"] and not reader["truncated"]
            assert reader["calls"] == len(reader["scopes"] or []) + reader["dropped_fast"]
            for scope in reader["scopes"] or []:
                assert scope["db_id"] == reader["db_id"]
                key = (reader["db_id"], scope["id"])
                assert key not in scopes
                scopes[key] = scope
                assert scope["start_us"] <= scope["latch_begin_us"] <= scope["latch_end_us"] <= scope["end_us"]
                assert scope["entry"]["space"] == scope["exit"]["space"]
                assert scope["entry"]["page"] == scope["exit"]["page"]
                assert bool(scope["trx"]) == bool(scope["pool_begin_us"])
                assert bool(scope["pool_begin_us"]) == bool(scope["pool_end_us"])
                for wait in scope["waits"] or []:
                    assert scope["latch_begin_us"] <= wait["register_us"] <= wait["return_us"] <= scope["latch_end_us"]
                    if wait["signal_before_us"]:
                        assert wait["register_us"] <= wait["signal_before_us"] <= wait["signal_after_us"] <= wait["return_us"]
                        assert wait["signal_before_us"] <= wait["resume_us"] <= wait["return_us"]
                        assert wait["notifier"]
                    else:
                        assert wait["signal_after_us"] == wait["resume_us"] == 0
                    waits.append(wait)
                if not run["control"] and scope["end_us"] - scope["start_us"] >= 100000:
                    assert len(scope["waits"]) == 1  # observed corpus, not an engine invariant
                    wait = scope["waits"][0]
                    assert wait["signal_before_us"] and wait["resume_us"]
                    names = [frame["function"].rsplit(".", 1)[-1] for frame in wait["notifier"]]
                    assert all(fn in names for fn in ("Fn217", "Fn16619", "Fn18174", "Fn18280"))
                    result["natural_long_waits"].append({
                        "run": run["name"], "db_id": reader["db_id"], "scope_id": scope["id"],
                        "space": scope["entry"]["space"], "page": scope["entry"]["page"],
                        "trx": scope["trx"], "pool_begin_called": bool(scope["pool_begin_us"]),
                        "scope_ms": round((scope["end_us"] - scope["start_us"]) / 1000, 3),
                        "register_to_signal_before_ms": round((wait["signal_before_us"] - wait["register_us"]) / 1000, 3),
                        "signal_after_to_resume_ms": round((wait["resume_us"] - wait["signal_after_us"]) / 1000, 3),
                    })
        result["processes"].append({"run": run["name"], "calls": sum(r["calls"] for r in readers),
                                    "retained_scopes": len(scopes), "park_events": len(waits)})
        assert len(run["captures"]) <= 1
        if not run["watcher"]:
            assert not run["captures"]
        for capture in run["captures"]:
            profile = (HERE / capture["retained_profile"]).read_bytes()
            assert hashlib.sha256(profile).hexdigest() == capture["profile_sha256"]
            assert len(profile) == capture["bytes"] and not capture["truncated"]
            assert capture["call_enter_us"] <= capture["snapshot_begin_us"] <= capture["snapshot_end_us"] <= capture["call_return_us"]
            if run["control"]:
                assert capture["phase"] == "positive_control" and not capture["read_before"] and not capture["read_after"]
                assert "p7.Fn5853" in profile.decode()
                continue
            assert capture["phase"] == "prepare"
            foreground = []
            for block in profile.decode().split("\n\n"):
                labels = next((json.loads(line[10:]) for line in block.splitlines() if line.startswith("# labels: ")), {})
                if labels.get("db_id") != capture["db_id"] or not labels.get("read_scope"):
                    continue
                if not re.search(r"\.Fn7142\+", block):
                    continue
                assert ".Fn18164+" in block and "base.AtomicWait+" in block
                scope_id = int(labels["read_scope"])
                scope = scopes[(capture["db_id"], scope_id)]
                wait = scope["waits"][0]
                for snapshots in (capture["read_before"], capture["read_after"]):
                    snap = next(s for s in snapshots if s["scope_id"] == scope_id)
                    assert snap["db_id"] == scope["db_id"] and snap["block"] == scope["block"] and snap["trx"] == scope["trx"]
                    assert snap["active_wait_ids"] == [wait["id"]]
                    assert wait["register_us"] <= snap["at_us"] <= wait["signal_before_us"]
                    assert snap["fields"]["space"] == scope["entry"]["space"] and snap["fields"]["page"] == scope["entry"]["page"]
                foreground.append(scope_id)
            assert len(foreground) == 1
            scope_id = foreground[0]
            row = next(v for v in result["natural_long_waits"] if v["run"] == run["name"] and v["db_id"] == capture["db_id"] and v["scope_id"] == scope_id)
            result["profile_bound_prepares"].append(dict(row, caller_ms=round((capture["call_return_us"] - capture["call_enter_us"]) / 1000, 3)))
    return result


