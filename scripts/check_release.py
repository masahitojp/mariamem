#!/usr/bin/env python3
"""Run only the generated-Go exact-source release guard (no publication)."""
import os
import subprocess
import sys
from common import ROOT
from release_version import require_tag

if os.environ.get("MARIAMEM_RELEASE_CONTRACT") not in (None, "generated-go-v1"):
    raise SystemExit("legacy release contracts are retired; use generated-go-v1")
if os.environ.get("MARIAMEM_RELEASE_TAG"):
    require_tag(os.environ["MARIAMEM_RELEASE_TAG"])
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
raise SystemExit(subprocess.call([sys.executable, str(ROOT/"scripts/release_generated_ci.py"),
                                 "guard", "--root", str(ROOT), "--candidate-sha", commit]))
