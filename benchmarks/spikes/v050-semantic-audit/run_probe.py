"""Run the isolated reviewed guest protocol and preserved failure oracles.

Exit zero means observations matched this investigation's receipt expectations;
the two correctness oracles must FAIL on the unmodified reviewed implementation.
That is never reported as runtime correctness PASS.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    a = p.parse_args()
    a.output = a.output.resolve()
    a.evidence = a.evidence.resolve()
    a.evidence.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GOTOOLCHAIN="go1.26.8")
    go = subprocess.check_output(["go", "version"], env=env, text=True).strip()
    assert go == "go version go1.26.8 darwin/arm64", "this receipt runner is the approved native macOS scope"
    identity = json.loads(subprocess.check_output([sys.executable, "scripts/git_identity.py", "inspect", "HEAD"], cwd=ROOT, text=True))
    subprocess.run([sys.executable, str(HERE/"package.py"), "--scan", str(ROOT/"docs/reviews/v050-access-paths-evidence"), "--output", str(a.output)], check=True)
    module = a.output/"module"
    rows = []

    def run(key, command, expected, backing="heap", meaning="functional"):
        started = datetime.now(timezone.utc).isoformat()
        log = a.evidence/(key+".txt")
        with log.open("w") as f:
            result = subprocess.run(command, cwd=module, env=dict(env, PROBE_BACKING=backing), stdout=f, stderr=subprocess.STDOUT, timeout=120)
        raw = log.read_text()
        rows.append({"key":key, "command":command, "backing":backing, "started_utc":started,
                     "exit_code":result.returncode, "expected_exit":expected,
                     "correctness_result":"FAIL" if result.returncode else "PASS", "meaning":meaning,
                     "race_reports":raw.count("WARNING: DATA RACE"), "log_sha256":sha(log)})
        (a.evidence/"probe-checkpoint.json").write_text(json.dumps(rows,indent=2)+"\n")
        assert result.returncode == expected, f"unexpected outcome: {key}; inspect {log}"
        return raw

    for backing in ("heap", "mmap"):
        for race in (False, True):
            key = "protocol-"+backing+("-race" if race else "")
            run(key,["go","test",*(["-race"] if race else []),"-count=1","-timeout=30s","-v","./probe"],0,backing)
    raw = run("timeout-boundary",["go","test","-count=1","-timeout=10s","-v","./internal/generatedgo/code/base","-run","^TestPositiveTimeoutMustNotExpireBeforeNotification$"],1,meaning="confirmed positive-timeout violation; expected failing oracle")
    assert "before notification" in raw
    raw = run("thread-boundary",["go","test","-count=1","-timeout=10s","-v","./internal/generatedgo/code/base","-run","^TestThreadIdentityBoundaries$"],1,meaning="confirmed TID boundary violations; counter seeded, not billions of guest launches")
    assert "spawn reported failure but child ran" in raw and "returned=0 child_ran=true contended=false" in raw
    raw = run("probe-vet",["go","vet","./probe","./internal/generatedgo/code/base"],1,meaning="FAIL: four unreachable-code diagnostics in byte-preserved generated bodies; not hidden or fixed in this study")
    assert raw.count("unreachable code") == 4 and len(raw.splitlines()) == 4
    binary = a.output/"protocol.test"
    run("probe-compile",["go","test","-c","-o",str(binary),"./probe"],0,meaning="isolated guest protocol compile")
    assembly = a.evidence/"mutex-arm64-disassembly.txt"
    with assembly.open("w") as f:
        subprocess.run(["go","tool","objdump","-s",r"probe.Fn(88|93|130)$|base.AtomicRmwCmpxchg32At$",str(binary)],env=env,stdout=f,check=True)
    data = {"source_identity":identity,"go_version":go,"checks":rows,
            "package_identity":json.loads((a.output/"identities.json").read_text()),
            "binary_sha256":sha(binary),"disassembly_sha256":sha(assembly),
            "scope":"20 byte-preserved guest function bodies and canonical host/base in isolated TLS/module; no full SQL guest run or canonical regeneration"}
    (a.evidence/"probe-results.json").write_text(json.dumps(data,indent=2)+"\n")
    print("Receipt saved: functional fixtures PASS; timeout and TID correctness oracles FAIL as reproduced")


if __name__ == "__main__":
    main()
