#!/usr/bin/env python3
"""Prepare the source candidate offline outside the repository and compare inputs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from common import ROOT, digest, extract

archive = ROOT / "build/release/mariamem-0.1.0a1-source-candidate.tar.gz"
expected = json.loads((ROOT / "build/prepared-source.json").read_text())["modified_files"]
with tempfile.TemporaryDirectory(prefix="mariamem-source-check-") as temporary:
    target = Path(temporary) / "unpack"
    extract(archive, target)
    project = target / "mariamem-0.1.0a1"
    subprocess.run([sys.executable, "scripts/check_public.py"], cwd=project, check=True)
    code = '''import sys, runpy, urllib.request
sys.path.insert(0, "scripts")
def offline(*args, **kwargs):
    raise RuntimeError("unexpected network access while preparing source candidate")
urllib.request.urlopen = offline
runpy.run_path("scripts/prepare_guest.py", run_name="__main__")
'''
    subprocess.run([sys.executable, "-c", code], cwd=project, check=True)
    for name, expected_hash in expected.items():
        if digest(project / "build/source" / name) != expected_hash:
            raise ValueError(f"source candidate differs from the built guest input: {name}")
report = {"passed": True, "source_candidate_sha256": digest(archive), "offline_prepare": True,
          "modified_files_match_built_guest": True, "files_checked": len(expected)}
(ROOT / "build/source-candidate-check.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
